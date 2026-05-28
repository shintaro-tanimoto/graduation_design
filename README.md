# 3D Power Diagram (Laguerre Voronoi) Generator

This tool generates 3D additively weighted Voronoi diagrams (Power Diagrams) with n-gon faces and sphere visualization.

## Usage

### Basic Usage

```bash
python LaguerreVoronoi.py
```

This reads from the default input file `input/sites.txt` and generates `output/sites.obj`.

### Specify Custom Input File

```bash
python LaguerreVoronoi.py input/sites_varied.txt
```

Output will be `output/sites_varied.obj` (filename matches input).

## Input File Format

Create a text file in `input/` directory with the following format:

```
# Comments start with #
# Format: x y z w
# where (x,y,z) is position and w is power weight

0 0 0 10
100 0 0 15
50 50 50 20
```

- Each line: `x y z w` (space-separated)
- `(x, y, z)`: 3D coordinates of site
- `w`: power weight (larger weight = larger cell)
- Lines starting with `#` are comments
- Empty lines are ignored

## Output

The program generates an OBJ file containing:

1. **Power Cells** (named `cell_0`, `cell_1`, ...)
   - n-gon faces (not triangulated)
   - Convex polyhedra

2. **Spheres** (named `sphere_0`, `sphere_1`, ...)
   - Radius = power weight `w`
   - Visual representation of site influence

## Visualization in Rhino

1. **Import OBJ file:**
   ```
   Command: Import
   File: output/sites.obj
   ```

2. **Select individual elements:**
   ```
   SelGroup "cell_0"    → Select cell 0
   SelGroup "sphere_*"  → Select all spheres
   ```

3. **Color assignment:**
   ```
   SelGroup "sphere_*"
   Properties → Object Color → Red

   SelGroup "cell_*"
   Properties → Display Mode → Ghosted
   ```

## Examples

### Example 1: Uniform Weights

`input/sites.txt` - All sites have equal weight (10)

```bash
python LaguerreVoronoi.py input/sites.txt
```

Result: Cells are similar in size.

### Example 2: Varied Weights

`input/sites_varied.txt` - Center has larger weight (25), corners have small weight (5)

```bash
python LaguerreVoronoi.py input/sites_varied.txt
```

Result: Center cell dominates (~59% of volume).

## Directory Structure

```
.
├── input/                  # Input text files
│   ├── sites.txt          # Default input
│   └── sites_varied.txt   # Example with varied weights
├── output/                 # Generated OBJ files
│   ├── sites.obj
│   └── sites_varied.obj
├── LaguerreVoronoi.py     # Main program
├── analyze_cells.py       # Volume analysis tool
└── analyze_faces.py       # Face structure analysis tool
```

## Analysis Tools

### Volume Analysis

```bash
python analyze_cells.py
```

Shows volume and coverage for each cell.

### Face Structure Analysis

```bash
python analyze_faces.py
```

Shows n-gon face distribution (3-gons, 4-gons, etc.).

## Notes

- Bounding box is automatically computed from site positions
- Larger weight → larger cell volume
- All faces are n-gons (not triangulated) for cleaner geometry
- Spheres visualize the influence radius of each site
