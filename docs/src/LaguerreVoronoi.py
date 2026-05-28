import numpy as np
from scipy.spatial import HalfspaceIntersection, ConvexHull

def power_halfspaces_for_cell(points, weights, i):
    """
    Return halfspaces A x <= b for Power cell of site i against all j.
    We use form: a·x <= b  (a is 3-vector, b scalar)
    From: 2(pj-pi)·x <= (|pj|^2-wj^2) - (|pi|^2-wi^2)
    Let a = (pj-pi), b = 0.5 * RHS so that a·x <= b
    """
    pi = points[i]
    wi = weights[i]
    hs = []
    for j in range(len(points)):
        if j == i:
            continue
        pj = points[j]
        wj = weights[j]
        a = (pj - pi)  # 3
        if np.linalg.norm(a) < 1e-12:
            continue
        b = 0.5 * ((pj @ pj - wj * wj) - (pi @ pi - wi * wi))
        hs.append((a, b))
    return hs

def box_halfspaces(box_min, box_max):
    """
    Axis-aligned box as halfspaces:
      x <= xmax, -x <= -xmin, similarly y,z
    Return list of (a,b) with a·x <= b
    """
    xmin, ymin, zmin = box_min
    xmax, ymax, zmax = box_max
    return [
        (np.array([ 1., 0., 0.]), xmax),
        (np.array([-1., 0., 0.]), -xmin),
        (np.array([ 0., 1., 0.]), ymax),
        (np.array([ 0.,-1., 0.]), -ymin),
        (np.array([ 0., 0., 1.]), zmax),
        (np.array([ 0., 0.,-1.]), -zmin),
    ]

def halfspaces_to_scipy(halfspaces):
    """
    scipy wants halfspaces in form: A x + b <= 0
    We have: a·x <= b  => a·x - b <= 0
    """
    H = []
    for a, b in halfspaces:
        H.append(np.append(a, -b))
    return np.array(H, dtype=float)

def find_interior_point(points, weights, i, box_min, box_max):
    """
    Need a feasible point inside all halfspaces for HalfspaceIntersection.
    Strategy: generate multiple candidate points moving from site toward box center.
    """
    pi = points[i].copy()
    c = 0.5 * (box_min + box_max)

    candidates = []

    # Candidate 1: site point slightly nudged toward center
    direction = c - pi
    if np.linalg.norm(direction) > 1e-6:
        for epsilon in [0.01, 0.05, 0.1, 0.2]:
            nudged = pi + epsilon * direction
            nudged = np.minimum(np.maximum(nudged, box_min), box_max)
            candidates.append(nudged)

    # Candidate 2: weighted average toward center
    for alpha in [0.3, 0.5, 0.7]:
        weighted = (1 - alpha) * pi + alpha * c
        weighted = np.minimum(np.maximum(weighted, box_min), box_max)
        candidates.append(weighted)

    # Candidate 3: box center (fallback)
    candidates.append(c)

    return candidates

def extract_polygon_faces(vertices, halfspaces, tol=1e-6):
    """
    Extract n-gon faces from convex polyhedron defined by vertices.
    Each face corresponds to one halfspace constraint.

    Returns:
        faces: list of vertex index lists (each face is an n-gon)
    """
    faces = []

    for a, b in halfspaces:
        # Find all vertices on this halfspace: a·v = b
        on_plane = []
        for idx, v in enumerate(vertices):
            dist = np.dot(a, v) - b
            if abs(dist) < tol:
                on_plane.append(idx)

        if len(on_plane) < 3:
            continue

        # Project vertices onto the plane to get 2D ordering
        face_verts = vertices[on_plane]

        # Create local 2D coordinate system on the plane
        normal = a / np.linalg.norm(a)

        # Find two orthogonal vectors in the plane
        if abs(normal[0]) < 0.9:
            u = np.cross(normal, [1, 0, 0])
        else:
            u = np.cross(normal, [0, 1, 0])
        u = u / np.linalg.norm(u)
        v = np.cross(normal, u)

        # Project face vertices to 2D
        face_2d = np.array([[np.dot(fv, u), np.dot(fv, v)] for fv in face_verts])

        # Compute centroid and sort by angle
        centroid = np.mean(face_2d, axis=0)
        angles = np.arctan2(face_2d[:, 1] - centroid[1],
                           face_2d[:, 0] - centroid[0])
        sorted_indices = np.argsort(angles)

        # Store face as ordered vertex indices
        face = [on_plane[i] for i in sorted_indices]
        faces.append(face)

    return faces

def compute_cell_polyhedron(points, weights, i, box_min, box_max, debug=False):
    hs = power_halfspaces_for_cell(points, weights, i) + box_halfspaces(box_min, box_max)
    H = halfspaces_to_scipy(hs)

    # try to find feasible interior point
    for idx, x0 in enumerate(find_interior_point(points, weights, i, box_min, box_max)):
        try:
            hs_int = HalfspaceIntersection(H, x0)
            verts = hs_int.intersections
            if verts is None or len(verts) < 4:
                if debug:
                    print(f"  x0[{idx}]: insufficient verts ({len(verts) if verts is not None else 0})")
                continue

            # Extract n-gon faces instead of triangulating
            faces = extract_polygon_faces(verts, hs)

            if debug:
                print(f"  x0[{idx}]: SUCCESS")
            return verts, faces
        except Exception as e:
            if debug:
                print(f"  x0[{idx}]: {type(e).__name__}: {e}")
            continue
    return None, None

def generate_sphere_mesh(center, radius, resolution=16):
    """
    Generate a UV sphere mesh.

    Args:
        center: (3,) array for sphere center
        radius: sphere radius
        resolution: number of segments (default 16)

    Returns:
        vertices: (N, 3) array
        faces: list of triangle indices
    """
    vertices = []
    faces = []

    # Generate vertices
    for i in range(resolution + 1):
        lat = np.pi * i / resolution - np.pi / 2  # -π/2 to π/2
        for j in range(resolution):
            lon = 2 * np.pi * j / resolution  # 0 to 2π

            x = center[0] + radius * np.cos(lat) * np.cos(lon)
            y = center[1] + radius * np.cos(lat) * np.sin(lon)
            z = center[2] + radius * np.sin(lat)
            vertices.append([x, y, z])

    # Generate faces (triangles)
    for i in range(resolution):
        for j in range(resolution):
            # Two triangles per quad
            v0 = i * resolution + j
            v1 = i * resolution + (j + 1) % resolution
            v2 = (i + 1) * resolution + j
            v3 = (i + 1) * resolution + (j + 1) % resolution

            if i < resolution:
                faces.append([v0, v2, v1])
                faces.append([v1, v2, v3])

    return np.array(vertices), faces

def extract_edges_from_faces(faces):
    """
    Extract unique edges from faces.

    Args:
        faces: list of vertex index lists (each face is an n-gon)

    Returns:
        edges: list of (v1, v2) tuples representing edges
    """
    edge_set = set()
    for face in faces:
        n = len(face)
        for i in range(n):
            v1 = face[i]
            v2 = face[(i + 1) % n]
            # Store edge with smaller index first to avoid duplicates
            edge = tuple(sorted([v1, v2]))
            edge_set.add(edge)
    return list(edge_set)

def is_cell_on_boundary(vertices, box_min, box_max, tol=1e-6):
    """
    Check if a cell touches the bounding box boundary.
    Note: Bottom face (Z=zmin) is excluded from boundary check.

    Args:
        vertices: (N, 3) array of cell vertices
        box_min: (3,) array of minimum bounds [xmin, ymin, zmin]
        box_max: (3,) array of maximum bounds [xmax, ymax, zmax]
        tol: tolerance for boundary detection

    Returns:
        bool: True if any vertex is on the boundary (excluding bottom face)
    """
    if vertices is None or len(vertices) == 0:
        return False

    for v in vertices:
        # Check if vertex is on any of the 5 boundary faces (excluding Z=zmin)
        if (abs(v[0] - box_min[0]) < tol or abs(v[0] - box_max[0]) < tol or
            abs(v[1] - box_min[1]) < tol or abs(v[1] - box_max[1]) < tol or
            abs(v[2] - box_max[2]) < tol):  # Only check Z=zmax, not Z=zmin
            return True

    return False

def export_obj(cells, path, sites=None, export_mode='faces'):
    """
    cells: list of (verts, faces) where faces are n-gons.
    sites: optional (N, 4) array [x, y, z, w] to export as spheres
    export_mode: 'faces' (default), 'edges', or 'both'
    Export as OBJ with groups per cell.

    Note: Converts Y-up to Z-up for Rhino (swaps Y and Z coordinates)
    """
    with open(path, "w", encoding="utf-8") as f:
        # First pass: collect all vertices and build global edge set
        all_vertices = []
        global_edges = set()  # Store edges as (coord1, coord2) tuples
        cell_info = []  # Store (V, F, start_idx) for each cell

        v_offset = 0
        for idx, (V, F) in enumerate(cells):
            if V is None:
                cell_info.append(None)
                continue

            start_idx = v_offset

            # Add vertices to global list (no coordinate transformation)
            for v in V:
                all_vertices.append((v[0], v[1], v[2]))

            # Collect edges if needed
            if export_mode in ['edges', 'both']:
                edges = extract_edges_from_faces(F)
                for v1, v2 in edges:
                    # Get actual vertex coordinates
                    coord1 = all_vertices[start_idx + v1]
                    coord2 = all_vertices[start_idx + v2]
                    # Normalize edge (smaller coord first) to avoid duplicates
                    edge = tuple(sorted([coord1, coord2]))
                    global_edges.add(edge)

            cell_info.append((V, F, start_idx))
            v_offset += len(V)

        # Write all vertices (no coordinate transformation)
        for v in all_vertices:
            f.write(f"v {v[0]} {v[1]} {v[2]}\n")

        # Write faces per cell group
        if export_mode in ['faces', 'both']:
            for idx, info in enumerate(cell_info):
                if info is None:
                    continue
                V, F, start_idx = info
                f.write(f"g cell_{idx}\n")
                for face in F:
                    # OBJ indices start at 1
                    f.write("f " + " ".join(str(i + start_idx + 1) for i in face) + "\n")

        # Write unique edges in a single group
        if export_mode in ['edges', 'both']:
            f.write(f"g edges\n")
            # Build reverse lookup: coord -> vertex index
            coord_to_idx = {}
            for i, coord in enumerate(all_vertices):
                coord_to_idx[coord] = i + 1  # OBJ indices start at 1

            for coord1, coord2 in global_edges:
                v1_idx = coord_to_idx[coord1]
                v2_idx = coord_to_idx[coord2]
                f.write(f"l {v1_idx} {v2_idx}\n")

        # Export sites as spheres (skip spheres in edges-only mode)
        if sites is not None and export_mode != 'edges':
            for idx, site in enumerate(sites):
                center = site[:3]
                radius = site[3]  # weight as radius

                sphere_verts, sphere_faces = generate_sphere_mesh(center, radius, resolution=16)

                f.write(f"g sphere_{idx}\n")
                for v in sphere_verts:
                    # No coordinate transformation
                    f.write(f"v {v[0]} {v[1]} {v[2]}\n")

                if export_mode in ['faces', 'both']:
                    for face in sphere_faces:
                        f.write("f " + " ".join(str(i + v_offset) for i in face) + "\n")

                if export_mode == 'both':
                    sphere_edges = extract_edges_from_faces(sphere_faces)
                    for v1, v2 in sphere_edges:
                        f.write(f"l {v1 + v_offset} {v2 + v_offset}\n")

                v_offset += len(sphere_verts)

def load_sites_from_file(filepath):
    """
    Load sites from text file.

    File format:
        - BOX xmin ymin zmin xmax ymax zmax (optional, first line)
        - Each line: x y z w (space-separated)
        - Lines starting with # are comments
        - Empty lines are ignored

    Args:
        filepath: path to text file

    Returns:
        sites: (N, 4) numpy array [x, y, z, w]
        box: tuple (box_min, box_max) or None if not specified
    """
    sites = []
    box = None

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            parts = line.split()

            # Check for BOX specification
            if parts[0].upper() == 'BOX':
                if len(parts) != 7:
                    raise ValueError(f"BOX format: BOX xmin ymin zmin xmax ymax zmax")
                xmin, ymin, zmin, xmax, ymax, zmax = map(float, parts[1:])
                box = (np.array([xmin, ymin, zmin]), np.array([xmax, ymax, zmax]))
                continue

            # Parse site data
            if len(parts) != 4:
                raise ValueError(f"Invalid line format: {line}")
            x, y, z, w = map(float, parts)
            sites.append([x, y, z, w])

    return np.array(sites, dtype=float), box

def compute_power_diagram(sites, box_min, box_max, output_path="power_cells.obj", export_spheres=True, export_mode='faces', remove_boundary_cells=False):
    """
    Compute 3D Power Diagram (Laguerre Voronoi) from sites with weights.

    Args:
        sites: (N, 4) array where each row is [x, y, z, w]
               or tuple of (P, W) where P is (N,3) and W is (N,)
        box_min: (3,) array for domain minimum [xmin, ymin, zmin]
        box_max: (3,) array for domain maximum [xmax, ymax, zmax]
        output_path: path to save OBJ file
        export_spheres: if True, export sites as spheres with radius = weight
        export_mode: 'faces', 'edges', or 'both' - controls what geometry to export
        remove_boundary_cells: if True, exclude cells that touch the bounding box boundary

    Returns:
        cells: list of (vertices, faces) tuples
    """
    # Handle both input formats
    sites_array = None
    if isinstance(sites, tuple):
        # Format: (P, W)
        P, W = sites
        P = np.asarray(P, dtype=float)
        W = np.asarray(W, dtype=float)
        # Create sites_array for sphere export
        sites_array = np.column_stack([P, W])
    else:
        # Format: (N, 4) array [x, y, z, w]
        sites = np.asarray(sites, dtype=float)
        if sites.ndim != 2 or sites.shape[1] != 4:
            raise ValueError("sites must be (N, 4) array or tuple (P, W)")
        P = sites[:, :3]
        W = sites[:, 3]
        sites_array = sites

    box_min = np.asarray(box_min, dtype=float)
    box_max = np.asarray(box_max, dtype=float)

    cells = []
    boundary_count = 0
    for i in range(len(P)):
        V, F = compute_cell_polyhedron(P, W, i, box_min, box_max, debug=False)

        # Check if we should exclude boundary cells (but keep cell0 and cell1)
        if remove_boundary_cells and V is not None and i not in [0, 1] and is_cell_on_boundary(V, box_min, box_max):
            print(f"Cell {i}: EXCLUDED (boundary cell)")
            cells.append((None, None))
            boundary_count += 1
        elif V is not None:
            print(f"Cell {i}: OK ({len(V)} vertices)")
            cells.append((V, F))
        else:
            print(f"Cell {i}: FAILED")
            cells.append((V, F))

    if output_path:
        export_obj(cells, output_path, sites=sites_array if export_spheres else None, export_mode=export_mode)
        print(f"exported: {output_path}")
        if export_spheres:
            print(f"  - {len(sites_array)} spheres included")
        print(f"  - export mode: {export_mode}")
        if remove_boundary_cells:
            print(f"  - {boundary_count} boundary cells excluded (bottom face not counted)")

    return cells

if __name__ == "__main__":
    import os
    import sys

    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)

    # Default input file
    input_file = "input/sites.txt"
    export_mode = "faces"  # default: export faces

    # Allow command-line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        mode = sys.argv[2].lower()
        if mode in ['faces', 'edges', 'both']:
            export_mode = mode
        else:
            print(f"Warning: Invalid export mode '{sys.argv[2]}', using 'faces'")

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        print("\nUsage:")
        print(f"  python {sys.argv[0]} [input_file] [export_mode]")
        print(f"\nArguments:")
        print(f"  input_file: path to input file (default: input/sites.txt)")
        print(f"  export_mode: 'faces', 'edges', or 'both' (default: faces)")
        sys.exit(1)

    # Load sites from file
    print(f"Loading sites from: {input_file}")
    sites, box_spec = load_sites_from_file(input_file)
    print(f"Loaded {len(sites)} sites")

    # Boundary box - use specified box or auto-compute from sites
    if box_spec is not None:
        box_min, box_max = box_spec
        print(f"Bounding box (specified): [{box_min[0]}, {box_min[1]}, {box_min[2]}] to [{box_max[0]}, {box_max[1]}, {box_max[2]}]")
    else:
        positions = sites[:, :3]
        box_min = np.floor(positions.min(axis=0))
        box_max = np.ceil(positions.max(axis=0))
        print(f"Bounding box (auto): [{box_min[0]}, {box_min[1]}, {box_min[2]}] to [{box_max[0]}, {box_max[1]}, {box_max[2]}]")

    # Output file name based on input file and export mode
    input_basename = os.path.splitext(os.path.basename(input_file))[0]
    if export_mode != "faces":
        output_file = f"output/{input_basename}_{export_mode}.obj"
    else:
        output_file = f"output/{input_basename}.obj"

    # Compute and export
    print(f"\nComputing Power Diagram (export mode: {export_mode})...")
    cells = compute_power_diagram(sites, box_min, box_max, output_file, export_spheres=True, export_mode=export_mode)

    print("\nDone!")
    print(f"Output: {output_file}")