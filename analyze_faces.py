"""Analyze face structure of OBJ file"""

def analyze_obj_faces(path):
    with open(path, 'r') as f:
        lines = f.readlines()

    cell_faces = {}
    current_cell = None

    for line in lines:
        line = line.strip()
        if line.startswith('g cell_'):
            current_cell = int(line.split('_')[1])
            cell_faces[current_cell] = []
        elif line.startswith('f '):
            parts = line.split()[1:]
            n_verts = len(parts)
            cell_faces[current_cell].append(n_verts)

    print("=" * 60)
    print("Face Structure Analysis (n-gon faces)")
    print("=" * 60)

    for cell_id in sorted(cell_faces.keys()):
        faces = cell_faces[cell_id]
        from collections import Counter
        face_counts = Counter(faces)

        print(f"\nCell {cell_id}:")
        print(f"  Total faces: {len(faces)}")
        for n in sorted(face_counts.keys()):
            count = face_counts[n]
            print(f"    {n}-gons: {count}")

    print("\n" + "=" * 60)
    print("Summary:")
    all_faces = [n for faces in cell_faces.values() for n in faces]
    from collections import Counter
    total_counts = Counter(all_faces)
    for n in sorted(total_counts.keys()):
        print(f"  Total {n}-gons: {total_counts[n]}")
    print(f"  Total faces: {len(all_faces)}")
    print("=" * 60)

if __name__ == "__main__":
    analyze_obj_faces("output/power_cells.obj")
