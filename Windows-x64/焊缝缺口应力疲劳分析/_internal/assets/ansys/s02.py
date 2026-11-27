# -*- coding: utf-8 -*-
# Pure ASCII file on purpose: runs in Mechanical IronPython 2.7 and CPython.
"""
02  FIRST SUBMODEL (+/-500 mm) - check (read-only, run after solving the first submodel)

What it does
  1. analysis settings: 12 steps, Large Deflection Off, Inertia Relief OFF, Direct solver
  2. boundary conditions: only the Imported Cut Boundary Constraint, no end loads, no extra supports
  3. section planes: surface stresses on rings at z = 13000 +/- (18...60, 100...450) mm,
     saved as Desktop/FAT_ANSYS/L1_sub500_planes.csv (script 03 compares the second submodel with it)
  4. comparison with the 26 m model (L0_full_planes.csv written by script 01) at +/-60...450 mm:
     differences > 5 % mean wrong step mapping in the cut boundary import, wrong coordinate system,
     or a cut boundary that is too close to the weld.
Output: Desktop/FAT_ANSYS/02_submodel_500_<time>.txt. Run time: about 2-5 min.
"""
ANALYSIS_INDEX = 0
COORDINATE_SYSTEM_NAME = "local"   # pipe system: z along the axis; first submodel without it uses the saved full-model local
WELD_Z_MM = None                   # None = automatic (middle of the model); or z of the weld in mm
R_OUT_MM = 147.0
R_IN_MM = 127.0
EXPECTED_STEPS = 12
TIMES_S = [float(i) for i in range(1, 13)]
PLANE_OFFSETS_MM = sorted([s * x for x in list(range(18, 61, 3)) + [80, 100, 150, 200, 300, 400, 450] for s in (-1, 1)])
KEEP_CHECK_RESULTS = False

#@COMMON@


def main():
    model = ExtAPI.DataModel.Project.Model
    analysis = model.Analyses[ANALYSIS_INDEX]
    cleanup(analysis)
    folder = desktop_folder(OUTPUT_FOLDER)
    out("02 first submodel check   analysis: {0}   {1}".format(analysis.Name, now_tag()))
    cs, frame = get_frame(model, COORDINATE_SYSTEM_NAME)
    check_settings(analysis, False, EXPECTED_STEPS)
    submodel_tree_check(analysis)
    rows, pts = plane_check(analysis, cs, frame, PLANE_OFFSETS_MM, TIMES_S, R_OUT_MM, R_IN_MM, now_tag())
    zlo, zhi = pts[0][1][2] - WELD_Z_MM, pts[-1][1][2] - WELD_Z_MM
    out("model extent relative to the weld: {0:+.1f} ... {1:+.1f} mm".format(zlo, zhi))
    if rows:
        save_planes(Path.Combine(folder, "L1_sub500_planes.csv"), "L1 submodel " + analysis.Name, rows)
        compare_planes(rows, Path.Combine(folder, "L0_full_planes.csv"), "26 m full model (script 01)")
        out("Note: near the weld (|offset| < 100 mm) the full model has no weld, small differences there are expected;")
        out("at +/-200...450 mm the two models must agree.")
    save_log(folder, "02_submodel_500")


with quiet():
    main()
