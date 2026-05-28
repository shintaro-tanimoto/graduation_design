import numpy as np
from scipy.spatial import ConvexHull

def analyze_obj(path):
    """
    Analyze the generated OBJ file and print statistics for each cell.
    """
    with open(path, 'r') as f:
        lines = f.readlines()

    cells = {}
    current_cell = None
    vertices = []
    faces = []

    for line in lines:
        line = line.strip()
        if line.startswith('g cell_'):
            # Save previous cell
            if current_cell is not None:
                cells[current_cell] = {
                    'vertices': np.array(vertices),
                    'faces': faces
                }
            # Start new cell
            current_cell = int(line.split('_')[1])
            vertices = []
            faces = []
        elif line.startswith('v '):
            parts = line.split()
            vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
        elif line.startswith('f '):
            parts = line.split()
            # OBJ uses 1-based indexing
            face = [int(p.split('/')[0]) for p in parts[1:]]
            faces.append(face)

    # Save last cell
    if current_cell is not None:
        cells[current_cell] = {
            'vertices': np.array(vertices),
            'faces': faces
        }

    # Print statistics
    print(f"{'Cell':<6} {'Verts':<8} {'Faces':<8} {'Volume':<12}")
    print("-" * 40)

    total_volume = 0
    for cell_id in sorted(cells.keys()):
        data = cells[cell_id]
        verts = data['vertices']
        n_faces = len(data['faces'])

        # Compute volume using ConvexHull
        if len(verts) >= 4:
            hull = ConvexHull(verts)
            volume = hull.volume
        else:
            volume = 0.0

        total_volume += volume
        print(f"{cell_id:<6} {len(verts):<8} {n_faces:<8} {volume:<12.2f}")

    print("-" * 40)
    print(f"Total: {len(cells)} cells, Volume: {total_volume:.2f}")
    print(f"Box volume: 100 x 100 x 100 = 1,000,000")
    print(f"Coverage: {total_volume / 1000000 * 100:.2f}%")

if __name__ == "__main__":
    analyze_obj("output/power_cells.obj")
