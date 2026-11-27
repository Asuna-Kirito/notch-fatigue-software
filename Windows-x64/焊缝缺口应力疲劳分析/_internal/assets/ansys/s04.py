# -*- coding: utf-8 -*-
# Pure ASCII file on purpose: runs in Mechanical IronPython 2.7 and CPython.
"""
04  SECOND SUBMODEL - export the six stress components on the FAT faces (run after solving)

Writes into Desktop/FAT_ANSYS (folder is created; files of an earlier run with the same names are overwritten):
  STEP_01_time_1.csv ... STEP_12_time_12.csv   body_id,node_id,SX..SXZ in MPa, coordinate system 'local'
  (STEP_13_time_13.csv when a 13th step with unit internal pressure exists; column sel when several selections)
  export_info.txt                              settings, constraint position, per-step checks
Script 05 writes the coordinates and the mesh into the same folder. Give the whole folder to the
software (New model). Size: about 60 bytes per node and step (20 000 nodes -> 1.2 MB per step).
Only result objects are added (and deleted at the end); loads, supports and mesh are not changed.
"""
SELECTION_NAME = "FAT"                    # named selection of the fillet faces; or ["FAT1", "FAT2"] (toes, roots)
COORDINATE_SYSTEM_NAME = "local"   # pipe system: z along the axis; first submodel without it uses the saved full-model local
CONSTRAINT_Z_MM = 13000.0                 # supports of the 26 m model, full-model convention (z = 0 at end A)
WELD_Z_MM = None                   # None = automatic (middle of the model); or z of the weld in mm
ANALYSIS_INDEX = 0
TIMES_S = [float(i) for i in range(1, 13)]
DIGITS = 9                                # significant digits written
KEEP_CHECK_RESULTS = False
COMPONENTS = ["SX", "SY", "SZ", "SXY", "SYZ", "SXZ"]

#@COMMON@


def main():
    model = ExtAPI.DataModel.Project.Model
    analysis = model.Analyses[ANALYSIS_INDEX]
    selections = get_selections(SELECTION_NAME)
    names = selection_names(SELECTION_NAME)
    multi = len(selections) > 1
    cs = find_coordinate_system(model, COORDINATE_SYSTEM_NAME)
    if not File.Exists("{0}".format(analysis.ResultFileName)):
        raise Exception("Solve the model first (result file not found)")
    cleanup(analysis)
    folder = desktop_folder(OUTPUT_FOLDER)
    info = ["format = notchfat-ansys-export-3", "selection = " + ",".join(names),
            "result_file = {0}".format(analysis.ResultFileName), "coordinate_system = " + COORDINATE_SYSTEM_NAME,
            "stress_unit = MPa", "constraint_z_mm = {0:g}".format(CONSTRAINT_Z_MM), "weld_z_mm = {0:g}".format(REF_WELD_Z_MM),
            "averaging = Mechanical Averaged; AverageAcrossBodies=False; body/node key retained",
            "exported = " + now_tag()]
    sol = analysis.Solution
    groups = []
    for si, selection in enumerate(selections):
        groups.append([user_result(sol, c, selection.Location, cs, "EXP{0}_{1}".format(si + 1, c)) for c in COMPONENTS])
    scope = None
    try:
        for k, t in enumerate(TIMES_S):
            rows = {}
            sel_of = {}
            for si, results in enumerate(groups):
                part = export_group(results, t)
                for key in part:
                    if key in rows:
                        raise Exception("Node {0} belongs to two selections".format(key))
                    rows[key] = part[key]
                    sel_of[key] = si + 1
            keys = sorted(rows)
            if scope is None:
                scope = keys
            elif keys != scope:
                raise Exception("Node set differs between load steps")
            peak = max(max(abs(v) for v in rows[q]) for q in keys)
            if peak <= 0.0:
                raise Exception("All stresses are zero at {0} s: is the unit load active in this step?".format(t))
            name = "STEP_{0:02d}_time_{1:g}.csv".format(k + 1, t)
            fmt = "{0:." + str(DIGITS) + "g}"
            lines = ["body_id,node_id,SX_MPa,SY_MPa,SZ_MPa,SXY_MPa,SYZ_MPa,SXZ_MPa" + (",sel" if multi else "")]
            for q in keys:
                lines.append("{0},{1},{2}".format(q[0], q[1], ",".join(fmt.format(v) for v in rows[q]))
                             + (",{0}".format(sel_of[q]) if multi else ""))
            write_text(Path.Combine(folder, name), "\n".join(lines) + "\n")
            info.append("step_{0:02d} = {1}; rows {2}; max |stress| {3:.4g} MPa".format(k + 1, name, len(keys), peak))
            out("step {0}: {1} rows, max |stress| {2:.4g} MPa".format(k + 1, len(keys), peak))
    finally:
        if not KEEP_CHECK_RESULTS:
            for results in groups:
                for r in results:
                    try:
                        r.Delete()
                    except Exception:
                        pass
    info.append("complete = true")
    write_text(Path.Combine(folder, "export_info.txt"), "\n".join(info) + "\n")
    out("EXPORT COMPLETE: " + folder)


def export_group(results, t):
    """Six stress components of one named selection at time t: {(body, node): [SX..SXZ]}."""
    rows = {}
    for ci, r in enumerate(results):
        r.DisplayTime = Quantity(float(t), "s")
        r.EvaluateAllResults()
        if not r.IsSolved:
            raise Exception("Result could not be evaluated: " + COMPONENTS[ci])
        if abs(float(r.Time.Value) - t) > 1e-6 * max(1.0, t):
            raise Exception("Requested/actual time mismatch at {0} s; step end times must be 1, 2, 3 ... s".format(t))
        table = r.PlotData
        table.ShowHiddenColumns = True
        nodes = read_native_column(table["Node"], "Node")
        raw = table["Values"]
        vals = read_native_column(raw, "Values")
        f = factor_to_mpa(str(raw.Unit))
        try:
            bodies = read_native_column(table["Body"], "Body")
        except Exception:
            bodies = [0] * len(nodes)
        for i in range(len(nodes)):
            key = (int(bodies[i]), int(nodes[i]))
            if ci == 0:
                rows[key] = [None] * 6
            elif key not in rows:
                raise Exception("Different node sets across components")
            v = float(vals[i]) * f
            if Double.IsNaN(v) or Double.IsInfinity(v):
                raise Exception("Non-finite stress at node {0}".format(key))
            rows[key][ci] = v
    return rows


with quiet():
    main()
