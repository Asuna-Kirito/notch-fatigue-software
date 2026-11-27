# -*- coding: utf-8 -*-
# Pure ASCII file on purpose: runs in Mechanical IronPython 2.7 and CPython.
"""
01  26 m FULL MODEL - check (read-only, run after solving the full model)

What it does
  1. analysis settings: 12 steps, Large Deflection Off, Inertia Relief On, Weak Springs Off, Direct solver
  2. loads: value of every load at the end of steps 1..12; each step must have exactly one non-zero unit load
  3. supports: position of the three support points (must be in the weld plane); reactions only if
     CHECK_REACTIONS = False            # True: add Force Reaction probes (may trigger a GUI JavaScript error) (off by default: the Force Reaction probe can make the Mechanical GUI show a
     JavaScript "support_vector_results" error; check reactions by hand instead, |R| < 1e-3 N)
  4. section planes: surface stresses on rings z = 13000 +/- 60...480 mm, saved as
     Desktop/FAT_ANSYS/L0_full_planes.csv; script 02 compares the first submodel with this file
Output: Desktop/FAT_ANSYS/01_full_model_<time>.txt. Temporary result objects are deleted again.
Run time: about 1-3 min (36 small evaluations).
"""
ANALYSIS_INDEX = 0                 # analysis in the tree (0 = first)
COORDINATE_SYSTEM_NAME = "local"   # pipe system: z along the axis; first submodel without it uses the saved full-model local
WELD_Z_MM = None                   # None = automatic (middle of the model); or z of the weld in mm
R_OUT_MM = 147.0                   # pipe outer radius
R_IN_MM = 127.0                    # pipe inner radius
EXPECTED_STEPS = 12
TIMES_S = [float(i) for i in range(1, 13)]
PLANE_OFFSETS_MM = [s * x for x in range(60, 481, 30) for s in (-1, 1)]
CHECK_REACTIONS = False            # True: add Force Reaction probes (may trigger a GUI JavaScript error)
KEEP_CHECK_RESULTS = False         # True keeps the temporary result objects in the tree

#@COMMON@


def load_face_z(obj, frame):
    """Local z (mm) of the centroid of the first face a load is applied to; None if not readable."""
    try:
        f = factor_to_mm(str(ExtAPI.DataModel.GeoData.Unit))
        ent = ExtAPI.DataModel.GeoData.GeoEntityById(int(list(obj.Location.Ids)[0]))
        c = [float(x) * f for x in ent.Centroid]
        return to_local(c, frame)[2]
    except Exception:
        return None


def support_positions(obj, frame):
    pos = []
    try:
        gunit = str(ExtAPI.DataModel.GeoData.Unit)
        f = factor_to_mm(gunit)
    except Exception:
        f = None
    try:
        ids = list(obj.Location.Ids)
    except Exception:
        ids = []
    for i in ids:
        try:
            ent = ExtAPI.DataModel.GeoData.GeoEntityById(int(i))
            p = [float(ent.X), float(ent.Y), float(ent.Z)]
            if f is not None:
                p = [x * f for x in p]
                pos.append(to_local(p, frame) if frame else p)
        except Exception:
            pass
    return pos


def reactions(analysis, supports, times):
    sol = analysis.Solution
    out("")
    out("== Support reactions (inertia relief: should be about 0) ==")
    worst = 0.0
    for sup in supports:
        probe = None
        try:
            with quiet():
                probe = sol.AddForceReaction()
                probe.Name = "CHK_reaction_" + sup.Name
            probe.BoundaryConditionSelection = sup
            vals = []
            for t in times:
                probe.DisplayTime = Quantity(float(t), "s")
                probe.EvaluateAllResults()
                q = probe.Total
                vals.append(abs(float(q.Value)) * (1000.0 if str(q.Unit).strip().lower() == "kn" else 1.0))
            worst = max(worst, max(vals))
            out("  {0}: max |R| over 12 steps = {1:.3g} N".format(sup.Name, max(vals)))
        except Exception as e:
            out("  {0}: reaction not readable by script ({1}); insert Force Reaction manually".format(sup.Name, e))
        finally:
            if probe is not None and not KEEP_CHECK_RESULTS:
                try:
                    probe.Delete()
                except Exception:
                    pass
    if worst > 0:
        check(worst < 1e-3, "largest reaction {0:.3g} N (unit load 1000 N; limit 1e-3 N)".format(worst))


def main():
    model = ExtAPI.DataModel.Project.Model
    analysis = model.Analyses[ANALYSIS_INDEX]
    folder = desktop_folder(OUTPUT_FOLDER)
    cleanup(analysis)
    out("01 full model check   analysis: {0}   {1}".format(analysis.Name, now_tag()))
    cs, frame = get_frame(model, COORDINATE_SYSTEM_NAME)
    if cs is None:
        raise Exception("The full model needs the coordinate system 'local' (z along the pipe axis)")
    save_frame(frame)
    pts = mesh_nodes_local(analysis, frame)
    resolve_weld_z(pts)
    zmin, zmax = pts[0][1][2], pts[-1][1][2]
    nsteps = check_settings(analysis, True, EXPECTED_STEPS)

    out("")
    out("== Loads and supports ==")
    loads, supports = [], []
    for obj in analysis.Children:
        cat = category(obj)
        if any(w in cat for w in ("AnalysisSettings", "Solution", "Initial", "Comment", "Figure", "Image", "Command")):
            continue
        supp = get(obj, "Suppressed", False) is True
        out("- {0} ({1}){2}".format(obj.Name, cat, "  [SUPPRESSED]" if supp else ""))
        if supp:
            continue
        if "Support" in cat or "Displacement" in cat:
            supports.append(obj)
            for p in support_positions(obj, frame):
                out("    point local (mm): x={0:.2f} y={1:.2f} z={2:.2f}".format(p[0], p[1], p[2]))
                check(abs(p[2] - WELD_Z_MM) < 1.0, "support z = {0:.2f} mm (weld plane {1:.2f})".format(p[2], WELD_Z_MM))
        else:
            vals = step_values(obj, nsteps)
            for comp in sorted(vals):
                out("    {0}: {1}".format(comp, ", ".join("{0:g}".format(x) for x in vals[comp])))
            loads.append((obj.Name, cat, vals, load_face_z(obj, frame)))
    out("")
    out("== Active load in each step ==")
    expected = [("Force", "Z", -1, "A"), ("Force", "X", 1, "A"), ("Force", "Y", 1, "A"),
                ("Moment", "Z", 1, "A"), ("Moment", "X", 1, "A"), ("Moment", "Y", 1, "A"),
                ("Force", "Z", 1, "B"), ("Force", "X", -1, "B"), ("Force", "Y", -1, "B"),
                ("Moment", "Z", -1, "B"), ("Moment", "X", -1, "B"), ("Moment", "Y", -1, "B")]
    for s in range(nsteps):
        act = []
        for name, cat, vals, zf in loads:
            for comp, v in sorted(vals.items()):
                if comp != "Magnitude" and s < len(v) and abs(v[s]) > 0:
                    act.append((name, cat, comp[0], v[s], zf))
        if len(act) != 1:
            check(False, "step {0}: {1} non-zero load components: {2}".format(s + 1, len(act), "; ".join(
                "{0} {1}={2:g}".format(a[0], a[2], a[3]) for a in act) or "none"))
            continue
        name, cat, ax, val, zf = act[0]
        kind = "Moment" if "Moment" in cat else "Force"
        mag = 1e6 if kind == "Moment" else 1000.0
        end = "?" if zf is None else ("A" if abs(zf - zmin) < 1.0 else ("B" if abs(zf - zmax) < 1.0 else "z={0:.0f}".format(zf)))
        txt = "step {0}: {1} {2}{3} = {4:g} on end {5}".format(s + 1, name, kind[0], ax, val, end)
        if s < len(expected):
            ek, ea, es, ee = expected[s]
            ok = kind == ek and ax == ea and abs(val - es * mag) < 1e-6 * mag and (end == ee or end == "?")
            txt += "   (expected {0}{1} = {2:g} on end {3})".format(ek[0], ea, es * mag, ee)
            check(ok, txt)
        else:
            out("          " + txt)
    out("Expected (software mapping, 1000 N / 1e6 N*mm): steps 1-6 at end A (smaller z): -FZ, +FX, +FY, +MZ, +MX, +MY;")
    out("steps 7-12 at end B (larger z): +FZ, -FX, -FY, -MZ, -MX, -MY. Check that each load is applied on the right end face.")
    if CHECK_REACTIONS and supports:
        reactions(analysis, supports, TIMES_S)

    rows, pts = plane_check(analysis, cs, frame, PLANE_OFFSETS_MM, TIMES_S, R_OUT_MM, R_IN_MM, now_tag(), pts)
    if rows:
        save_planes(Path.Combine(folder, "L0_full_planes.csv"), "L0 full model " + analysis.Name, rows)
    save_log(folder, "01_full_model")


with quiet():
    main()
