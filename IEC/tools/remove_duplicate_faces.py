#!/usr/bin/env python3
"""
Remove duplicate faces from OBJ file.
"""
import sys
from pathlib import Path


def parse_face_indices(face_str):
    """
    Parse face string and return tuple of vertex indices.
    Handles formats: f v1 v2 v3, f v1/vt1 v2/vt2 v3/vt3, f v1//vn1 v2//vn2 v3//vn3, etc.
    """
    indices = []
    for vertex_data in face_str.split():
        # Split by '/' and take the first part (vertex index)
        v_idx = vertex_data.split('/')[0]
        indices.append(int(v_idx))
    return tuple(indices)


def normalize_face(face_indices):
    """
    Normalize face by sorting indices to detect duplicates regardless of vertex order.
    Returns a tuple of sorted indices.
    """
    return tuple(sorted(face_indices))


def remove_duplicate_faces(input_path, output_path=None):
    """
    Remove duplicate faces from OBJ file.

    Args:
        input_path: Path to input OBJ file
        output_path: Path to output OBJ file (if None, adds '_cleaned' suffix)
    """
    input_path = Path(input_path)

    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_cleaned{input_path.suffix}"
    else:
        output_path = Path(output_path)

    print(f"Reading: {input_path}")

    # Read OBJ file
    vertices = []
    faces = []
    other_lines = []

    with open(input_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                other_lines.append(line)
            elif line.startswith('v '):
                vertices.append(line)
            elif line.startswith('f '):
                # Parse face indices
                face_data = line[2:].strip()
                face_indices = parse_face_indices(face_data)
                faces.append((line, face_indices))
            else:
                other_lines.append(line)

    print(f"Total vertices: {len(vertices)}")
    print(f"Total faces: {len(faces)}")

    # Remove duplicate faces
    seen_faces = set()
    unique_faces = []
    duplicate_count = 0

    for face_line, face_indices in faces:
        normalized = normalize_face(face_indices)
        if normalized not in seen_faces:
            seen_faces.add(normalized)
            unique_faces.append(face_line)
        else:
            duplicate_count += 1

    print(f"Duplicate faces found: {duplicate_count}")
    print(f"Unique faces: {len(unique_faces)}")

    # Write cleaned OBJ file
    with open(output_path, 'w') as f:
        # Write comments and other lines at the beginning
        for line in other_lines:
            if line.startswith('#') or not line:
                f.write(line + '\n')

        # Write vertices
        for v in vertices:
            f.write(v + '\n')

        # Write unique faces
        for face in unique_faces:
            f.write(face + '\n')

    print(f"Cleaned OBJ saved to: {output_path}")
    print(f"Removed {duplicate_count} duplicate faces ({duplicate_count / len(faces) * 100:.2f}%)")

    return output_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python remove_duplicate_faces.py <input.obj> [output.obj]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    remove_duplicate_faces(input_file, output_file)
