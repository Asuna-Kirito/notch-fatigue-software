# -*- coding: utf-8 -*-
# Pure ASCII file on purpose: runs in Mechanical IronPython 2.7 and CPython.
"""
03  SECOND SUBMODEL (the one with the 1 mm fillets) - check (read-only, run after solving it)

What it does
  1. analysis settings: 12 steps, Large Deflection Off, Inertia Relief OFF, Direct solver
  2. boundary conditions: only the Imported Cut Boundary Constraint
  3. cut distance: axial extent of the model and of the FAT faces -> free length between the
     outer edge of the toe fillet and each cut face (recommended >= 20 mm = one wall thickness)
  4. section planes between the toe and the cut faces (every 2 mm, weld region skipped automatically),
     compared with the first submodel (L1_sub500_planes.csv written by script 02).
     The plane nearest to each cut face is the decisive one: <= 2 % means the cut is far enough.
Output: Desktop/FAT_ANSYS/03_submodel_fillet_<time>.txt and L2_fillet_planes.csv. Run time: about 2-5 min.
"""
ANALYSIS_INDEX = 0
COORDINATE_SYSTEM_NAME = "local"   # pipe system: z along the axis; first submodel without it uses the saved full-model local
WELD_Z_MM = None                   # None = automatic (middle of the model); or z of the weld in mm
R_OUT_MM = 147.0
R_IN_MM = 127.0
EXPECTED_STEPS = 12
TIMES_S = [float(i) for i in range(1, 13)]
FAT_SELECTION = "FAT"
PLANE_OFFSETS_MM = sorted([s * x for x in range(14, 81, 2) for s in (-1, 1)])
RECOMMENDED_FREE_LENGTH_MM = 20.0
KEEP_CHECK_RESULTS = False

#@COMMON@


def main():
    model = ExtAPI.DataModel.Project.Model
    analysis = model.Analyses[ANALYSIS_INDEX]
    cleanup(analysis)
    folder = desktop_folder(OUTPUT_FOLDER)
    out("03 second submodel check   analysis: {0}   {1}".format(analysis.Name, now_tag()))
    cs, frame = get_frame(model, COORDINATE_SYSTEM_NAME)
    check_settings(analysis, False, EXPECTED_STEPS)
    submodel_tree_check(analysis)
    pts = mesh_nodes_local(analysis, frame)
    resolve_weld_z(pts, fat_z_range(analysis, frame, FAT_SELECTION, absolute=True))
    rows, pts = plane_check(analysis, cs, frame, PLANE_OFFSETS_MM, TIMES_S, R_OUT_MM, R_IN_MM, now_tag(), pts)
    zlo, zhi = pts[0][1][2] - WELD_Z_MM, pts[-1][1][2] - WELD_Z_MM
    out("")
    out("== Cut distance ==")
    out("model extent relative to the weld: {0:+.2f} ... {1:+.2f} mm".format(zlo, zhi))
    fr = fat_z_range(analysis, frame, FAT_SELECTION)
    if fr is not None:
        out("FAT faces (toe fillets) extend over {0:+.2f} ... {1:+.2f} mm".format(fr[0], fr[1]))
        left, right = fr[0] - zlo, zhi - fr[1]
        check(left >= RECOMMENDED_FREE_LENGTH_MM, "free length fillet -> left cut face  = {0:.1f} mm (>= {1:g})".format(left, RECOMMENDED_FREE_LENGTH_MM))
        check(right >= RECOMMENDED_FREE_LENGTH_MM, "free length fillet -> right cut face = {0:.1f} mm (>= {1:g})".format(right, RECOMMENDED_FREE_LENGTH_MM))
    else:
        out("named selection '{0}' not found; free length not computed".format(FAT_SELECTION))
    if rows:
        save_planes(Path.Combine(folder, "L2_fillet_planes.csv"), "L2 submodel " + analysis.Name, rows)
        compare_planes(rows, Path.Combine(folder, "L1_sub500_planes.csv"), "first submodel (script 02)")
        offs = sorted(set(float(r.split(",")[0]) for r in rows))
        out("Decisive planes (nearest to the cut faces): {0:+g} mm and {1:+g} mm".format(offs[0], offs[-1]))
    else:
        out("No plane between the toe and the cut faces: the cut is too close to the weld (extend it).")
    save_log(folder, "03_submodel_fillet")


with quiet():
    main()
