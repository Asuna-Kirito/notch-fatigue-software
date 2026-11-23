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

# ------------------------------------------------------------------ common block (same in scripts 01-06)
import math
from System import Environment, DateTime, Double
from System.IO import Directory, File, Path, StreamWriter, StreamReader
from System.Text import UTF8Encoding

LOG = []
OUTPUT_FOLDER = "FAT_ANSYS"     # all scripts 01-06 write into Desktop/FAT_ANSYS


def out(s=""):
    LOG.append("{0}".format(s))
    print(s)


def get(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


def factor_to_mpa(unit):
    key = str(unit).strip().replace(" ", "").lower()
    factors = {"pa": 1e-6, "kpa": 1e-3, "mpa": 1., "gpa": 1000., "n/mm^2": 1., "n/mm2": 1.,
               "psi": .006894757293168, "ksi": 6.894757293168}
    if key not in factors:
        raise Exception("Unknown stress unit: " + str(unit))
    return factors[key]


def factor_to_mm(unit):
    key = str(unit).strip().replace(" ", "").lower()
    factors = {"m": 1000., "meter": 1000., "mm": 1., "millimeter": 1., "cm": 10., "um": 1e-3,
               "micron": 1e-3, "in": 25.4, "inch": 25.4, "ft": 304.8, "foot": 304.8}
    if key not in factors:
        raise Exception("Unknown length unit: " + str(unit))
    return factors[key]


def desktop_folder(name):
    root = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory)
    path = Path.Combine(root, name)
    if not Directory.Exists(path):
        Directory.CreateDirectory(path)
    return path


def write_text(path, text):
    w = StreamWriter(path, False, UTF8Encoding(True))
    try:
        w.Write(text)
    finally:
        w.Close()


def read_lines(path):
    r = StreamReader(path, UTF8Encoding(True))
    try:
        return [x for x in r.ReadToEnd().replace("\r", "").split("\n") if x.strip()]
    finally:
        r.Close()


def now_tag():
    return str(DateTime.Now.ToString("yyyyMMdd_HHmmss"))


def native_type_name(value):
    try:
        return str(value.GetType().FullName)
    except Exception:
        return str(type(value).__name__)


def read_native_column(column, label):
    if column is None:
        raise Exception("Result column is None: " + label)
    for attribute in ("Count", "Length"):
        try:
            count = int(getattr(column, attribute))
        except Exception:
            continue
        return [column[index] for index in range(count)]
    return [v for v in column]


def print_frame(label, fr):
    o, ax = fr
    out("{0} in global mm: origin ({1:.3f}, {2:.3f}, {3:.3f}); x ({4:.5f}, {5:.5f}, {6:.5f}); "
        "y ({7:.5f}, {8:.5f}, {9:.5f}); z ({10:.5f}, {11:.5f}, {12:.5f})".format(
            label, o[0], o[1], o[2], ax[0][0], ax[0][1], ax[0][2], ax[1][0], ax[1][1], ax[1][2], ax[2][0], ax[2][1], ax[2][2]))


def find_coordinate_system(model, name, required=True):
    """The pipe coordinate system 'local' (z along the pipe axis, origin on the axis). None if missing and not required."""
    systems = list(model.CoordinateSystems.Children)
    matches = [cs for cs in systems if cs.Name == name]
    if len(matches) > 1:
        raise Exception("More than one coordinate system named '{0}'".format(name))
    if not matches:
        if required:
            raise Exception("Coordinate system '{0}' not found in this model. Available: {1}".format(
                name, ", ".join("{0}".format(cs.Name) for cs in systems)))
        return None
    cs = matches[0]
    if str(cs.CoordinateSystemType).split(".")[-1] != "Cartesian":
        raise Exception("Coordinate system '{0}' must be Cartesian".format(name))
    fr = coordinate_frame(cs)
    if fr is not None:
        print_frame("Coordinate system '{0}'".format(name), fr)
    return cs


FRAME_FILE = "local_frame_full_model.txt"


def save_frame(fr):
    """Written by script 01: 'local' of the full model in global coordinates, used by models without 'local'."""
    o, ax = fr
    vals = o + ax[0] + ax[1] + ax[2]
    path = Path.Combine(desktop_folder(OUTPUT_FOLDER), FRAME_FILE)
    write_text(path, " ".join("{0:.12g}".format(v) for v in vals) + "\n")
    out("local of the full model saved for the submodels: " + path)


def load_frame():
    path = Path.Combine(desktop_folder(OUTPUT_FOLDER), FRAME_FILE)
    if not File.Exists(path):
        return None
    v = [float(x) for x in read_lines(path)[0].split()]
    return v[0:3], [v[3:6], v[6:9], v[9:12]]


def get_frame(model, name):
    """(cs, frame). With 'local' in the model: that system. Without it (first submodel): the 'local' of the
    full model saved by script 01; stresses are then read in the global system and rotated by the script.
    Submodels share the global coordinates of the full model, so the saved frame applies to them unchanged."""
    cs = find_coordinate_system(model, name, required=False)
    if cs is not None:
        fr = coordinate_frame(cs)
        if fr is None:
            raise Exception("Origin/axes of '{0}' not readable".format(name))
        check_against_saved(fr)
        return cs, fr
    fr = load_frame()
    if fr is None:
        raise Exception("No coordinate system '{0}' in this model and no saved frame. Run script 01 in the full model "
                        "first (it saves its 'local'), or create '{0}' here with the same origin and axes.".format(name))
    out("No coordinate system '{0}' in this model: using the 'local' of the full model saved by script 01.".format(name))
    print_frame("Saved local", fr)
    out("  Stress components are read in the global system and rotated to these axes by the script.")
    return None, fr


def check_against_saved(fr):
    """Axes must equal the full model's 'local'; the origin may move only along the axis."""
    sv = load_frame()
    if sv is None:
        return
    o, ax = fr
    so, sax = sv
    dots = [sum(ax[k][i] * sax[k][i] for i in range(3)) for k in range(3)]
    d = [o[i] - so[i] for i in range(3)]
    along = sum(d[i] * sax[2][i] for i in range(3))
    perp = sum((d[i] - along * sax[2][i]) ** 2 for i in range(3)) ** 0.5
    check(min(dots) > 0.99999, "axes equal to the full model 'local' (cos = {0:.6f}, {1:.6f}, {2:.6f})".format(*dots))
    check(perp < 0.5, "origin on the same pipe axis as the full model 'local' (offset {0:.3f} mm; shift along the axis "
          "{1:.1f} mm is allowed)".format(perp, along))


def _vec(v):
    for names in (("X", "Y", "Z"), ("x", "y", "z")):
        try:
            return [float(getattr(v, names[0])), float(getattr(v, names[1])), float(getattr(v, names[2]))]
        except Exception:
            pass
    lst = [float(a) for a in v]
    if len(lst) != 3:
        raise Exception("Cannot read vector " + native_type_name(v))
    return lst


def _qty_mm(q):
    try:
        return float(q.Value) * factor_to_mm(str(q.Unit))
    except Exception:
        return None


def coordinate_frame(cs):
    """Origin (mm, global) and unit axes of a Cartesian system; None if the API does not expose them."""
    if get(cs, "IsGlobal", False) is True:
        return [0.0, 0.0, 0.0], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    try:
        origin = [_qty_mm(cs.OriginX), _qty_mm(cs.OriginY), _qty_mm(cs.OriginZ)]
        if None in origin:
            return None
        axes = []
        for name in ("XAxis", "YAxis", "ZAxis"):
            a = _vec(getattr(cs, name))
            n = (a[0] ** 2 + a[1] ** 2 + a[2] ** 2) ** 0.5
            axes.append([a[0] / n, a[1] / n, a[2] / n])
        return origin, axes
    except Exception:
        return None


def to_local(p, frame):
    o, ax = frame
    d = [p[0] - o[0], p[1] - o[1], p[2] - o[2]]
    return [d[0] * a[0] + d[1] * a[1] + d[2] * a[2] for a in ax]


def walk(obj):
    """All objects below obj in the tree."""
    res = []
    for c in list(get(obj, "Children", []) or []):
        res.append(c)
        res.extend(walk(c))
    return res


def category(obj):
    return str(get(obj, "DataModelObjectCategory", "")).split(".")[-1]


def check(flag, text):
    out(("[OK]      " if flag else "[CHANGE]  ") + text)
    return flag


def check_settings(analysis, expect_ir, expected_steps):
    st = analysis.AnalysisSettings
    out("== Analysis settings ==")
    nsteps = int(get(st, "NumberOfSteps", 0) or 0)
    check(nsteps == expected_steps, "Number of steps = {0} (expected {1})".format(nsteps, expected_steps))
    ld = get(st, "LargeDeflection")
    check(ld is False, "Large Deflection = {0} (must be Off: unit loads are superposed linearly)".format(ld))
    ir = get(st, "InertiaRelief")
    check(ir is expect_ir, "Inertia Relief = {0} (expected {1})".format(ir, "On" if expect_ir else "Off"))
    ws = str(get(st, "WeakSprings"))
    check("Off" in ws or "ProgramControlled" in ws, "Weak Springs = {0} (Off)".format(ws))
    sv = str(get(st, "SolverType"))
    check("Direct" in sv or "ProgramControlled" in sv or "Iterative" in sv,
          "Solver Type = {0} (Direct; Iterative is fine for large submodels with tolerance <= 1e-8)".format(sv))
    return nsteps


def _times_s(var):
    out_ = []
    for q in var.DiscreteValues:
        try:
            u = str(q.Unit).strip().lower()
            f = 60.0 if u in ("min",) else 3600.0 if u in ("hr", "h") else 1.0
            out_.append(float(q.Value) * f)
        except Exception:
            out_.append(float(q))
    return out_


def _value_at(times, vals, t):
    """Value of a tabular load at time t (Mechanical ramps linearly between table rows)."""
    for k in range(len(times)):
        if abs(times[k] - t) < 1e-9 * max(1.0, abs(t)):
            return vals[k]
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    for k in range(len(times) - 1):
        if times[k] < t < times[k + 1]:
            w = (t - times[k]) / (times[k + 1] - times[k])
            return vals[k] * (1 - w) + vals[k + 1] * w
    return vals[-1]


def step_values(obj, nsteps):
    """{component: [value at the end time of step 1..n]}; end time of step k = k s.
    The table of a load has its own time points (Inputs[0]); values are read at t = 1, 2, ... n s."""
    res = {}
    for comp in ("Magnitude", "XComponent", "YComponent", "ZComponent"):
        v = get(obj, comp)
        if v is None:
            continue
        try:
            dv = v.Output.DiscreteValues
            vals = [float(dv[i].Value) for i in range(int(dv.Count))]
        except Exception:
            continue
        if not vals:
            continue
        times = None
        try:
            times = _times_s(v.Inputs[0])
            if len(times) != len(vals):
                times = None
        except Exception:
            times = None
        if times is None:
            if len(vals) == 1:
                times = [0.0]
            elif len(vals) == nsteps + 1:
                times = [float(i) for i in range(nsteps + 1)]
            else:
                out("    {0}.{1}: {2} table values without readable times; not checked".format(obj.Name, comp, len(vals)))
                continue
        res[comp] = [_value_at(times, vals, float(k)) for k in range(1, nsteps + 1)]
    return res


class _Multi(object):
    def __init__(self, items):
        self.items = items
        self.entered = []

    def __enter__(self):
        for it in self.items:
            try:
                it.__enter__()
                self.entered.append(it)
            except Exception:
                pass
        return self

    def __exit__(self, *args):
        for it in reversed(self.entered):
            try:
                it.__exit__(None, None, None)
            except Exception:
                pass
        self.entered = []
        return False


def quiet():
    """Suspends graphics updates while the script runs (Graphics.Suspend, Mechanical 2021 R1 and later)."""
    ctx = []
    for maker in ("Graphics.Suspend()", "ExtAPI.Graphics.Suspend()"):
        try:
            ctx.append(eval(maker))
            break
        except Exception:
            pass
    return _Multi(ctx)


def cleanup(analysis):
    """Deletes temporary objects left by an earlier run that was interrupted."""
    n = 0
    for obj in list(analysis.Solution.Children):
        name = "{0}".format(get(obj, "Name", ""))
        if name.startswith("CHK_") or name.startswith("EXP_") or name.startswith("PK_"):
            try:
                obj.Delete()
                n += 1
            except Exception:
                pass
    if n:
        print("removed {0} temporary objects of an earlier run".format(n))


# ---------------- stress on a set of nodes, evaluated at the end of each step
def user_result(solution, expression, location, cs, name):
    with quiet():
        r = solution.AddUserDefinedResult()
        r.Name = name
        r.Expression = expression
        r.OutputUnit = UnitCategoryType.Stress
        r.Location = location
        if cs is not None:
            r.CoordinateSystem = cs
    r.DisplayOption = ResultAveragingType.Averaged
    try:
        r.AverageAcrossBodies = False
    except Exception:
        pass
    try:
        r.CalculateTimeHistory = False
    except Exception:
        pass
    r.By = SetDriverStyle.Time
    return r


def evaluate(result, time_s):
    """{node: value MPa} at the given time; nodes shared by two bodies are averaged."""
    result.DisplayTime = Quantity(float(time_s), "s")
    result.EvaluateAllResults()
    if not result.IsSolved:
        raise Exception("Result could not be evaluated: " + result.Name)
    actual = float(result.Time.Value)
    if abs(actual - float(time_s)) > 1e-6 * max(1., abs(float(time_s))):
        raise Exception("Requested time {0} s but got {1} s; step end times must be 1, 2, ... 12 s".format(time_s, actual))
    table = result.PlotData
    table.ShowHiddenColumns = True
    nodes = read_native_column(table["Node"], "Node")
    raw = table["Values"]
    vals = read_native_column(raw, "Values")
    f = factor_to_mpa(str(raw.Unit))
    acc = {}
    for i in range(len(nodes)):
        n = int(nodes[i])
        v = float(vals[i]) * f
        if n in acc:
            acc[n][0] += v
            acc[n][1] += 1
        else:
            acc[n] = [v, 1]
    return dict((n, s / c) for n, (s, c) in acc.items())


def node_location(ids):
    sel = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.MeshNodes)
    try:
        from System.Collections.Generic import List
        sel.Ids = List[int]([int(i) for i in ids])
    except Exception:
        sel.Ids = [int(i) for i in ids]
    return sel


# ---------------- section-plane check: Fourier fit of the surface stresses on rings at fixed z
def mesh_nodes_local(analysis, frame):
    mesh = analysis.MeshData
    f = factor_to_mm(str(mesh.Unit))
    pts = []
    try:
        for nd in mesh.Nodes:
            g = [float(nd.X) * f, float(nd.Y) * f, float(nd.Z) * f]
            pts.append((int(nd.Id), to_local(g, frame)))
    except Exception:
        pts = []
        for n in list(mesh.NodeIds):
            nd = mesh.NodeById(n)
            g = [float(nd.X) * f, float(nd.Y) * f, float(nd.Z) * f]
            pts.append((int(n), to_local(g, frame)))
    pts.sort(key=lambda t: t[1][2])
    return pts


REF_WELD_Z_MM = 13000.0   # weld plane in the full-model convention (z = 0 at end A); used for exported z


def resolve_weld_z(pts, fat_range=None):
    """Weld mid-plane (mm, in the chosen coordinate system).
    WELD_Z_MM = None: middle of the model's axial extent (full model 0..26000 -> 13000; submodels are cut
    symmetrically about the weld). With FAT faces the middle of the two toe fillets is reported as a check."""
    global WELD_Z_MM
    zmin, zmax = pts[0][1][2], pts[-1][1][2]
    if WELD_Z_MM is None:
        WELD_Z_MM = 0.5 * (zmin + zmax)
        out("Weld plane located automatically: z = {0:.3f} mm (middle of the model, z from {1:.3f} to {2:.3f})".format(
            WELD_Z_MM, zmin, zmax))
    else:
        out("Weld plane set by hand: z = {0:.3f} mm (model z from {1:.3f} to {2:.3f})".format(WELD_Z_MM, zmin, zmax))
    if fat_range is not None:
        mid = 0.5 * (fat_range[0] + fat_range[1])
        check(abs(mid - WELD_Z_MM) < 1.0, "middle of the FAT fillets z = {0:.3f} mm (should equal the weld plane)".format(mid))
    return WELD_Z_MM


def _first_at_least(zs, z):
    lo, hi = 0, len(zs)
    while lo < hi:
        mid = (lo + hi) // 2
        if zs[mid] < z:
            lo = mid + 1
        else:
            hi = mid
    return lo


def pick_planes(pts, offsets, r_out, r_in, tol_r=0.3, max_ring=360, min_ring=24):
    """Rings of surface nodes (outer, inner) at z = WELD_Z_MM + offset; planes in the weld are skipped."""
    zs = [p[1][2] for p in pts]
    zmin, zmax = zs[0], zs[-1]
    planes, notes = [], []
    for off in offsets:
        z0 = WELD_Z_MM + off
        if z0 < zmin + 0.4 or z0 > zmax - 0.4:
            continue
        band, rings, ok = 0.25, None, False
        while band <= 40.0:
            i0, i1 = _first_at_least(zs, z0 - band), _first_at_least(zs, z0 + band + 1e-9)
            outer, inner, weld = [], [], False
            for k in range(i0, i1):
                n, p = pts[k]
                r = (p[0] ** 2 + p[1] ** 2) ** 0.5
                if r > r_out + 0.5 or r < r_in - 0.5:
                    weld = True
                    break
                th = math.atan2(p[1], p[0])
                if abs(r - r_out) < tol_r:
                    outer.append((th, n, p[2] - z0))
                elif abs(r - r_in) < tol_r:
                    inner.append((th, n, p[2] - z0))
            if weld:
                break
            if len(outer) >= min_ring and len(inner) >= min_ring and _coverage(outer) and _coverage(inner):
                rings, ok = (outer, inner), True
                break
            band *= 2.0
        if not ok:
            notes.append("plane {0:+g} mm skipped ({1})".format(off, "weld or fillet inside the band" if weld else "too few surface nodes"))
            continue
        res = []
        for name, ring in zip(("outer", "inner"), rings):
            ring = _single_layer(ring, min_ring)
            ring.sort()
            if len(ring) > max_ring:
                step = len(ring) / float(max_ring)
                ring = [ring[int(i * step)] for i in range(max_ring)]
            res.append((name, ring))
        planes.append((off, band, res))
    return planes, notes


def _single_layer(ring, min_ring):
    """Keep only the nodes of one axial node layer (the one nearest to the requested z that still covers the
    circumference). A ring spread over several z layers makes the fit of the mean value ill-conditioned."""
    groups = {}
    for t in ring:
        groups.setdefault(int(round(t[2] / 0.005)), []).append(t)
    best = None
    for g in groups.values():
        if len(g) < min_ring or not _coverage(g):
            continue
        dz = abs(sum(t[2] for t in g) / len(g))
        if best is None or dz < best[0] - 1e-6 or (abs(dz - best[0]) <= 1e-6 and len(g) > len(best[1])):
            best = (dz, g)
    return list(best[1]) if best is not None else list(ring)


def _coverage(ring):
    th = sorted(t[0] for t in ring)
    gaps = [th[i + 1] - th[i] for i in range(len(th) - 1)] + [th[0] + 2 * math.pi - th[-1]]
    return max(gaps) < math.pi / 3


def _solve(A, b):
    n = len(b)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-300:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                fct = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= fct * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def fourier_fit(samples):
    """samples: (theta, dz, value) -> ([c0, c1, s1], z_eff) of value = c0 + c1 cos + s1 sin (+ d * (dz - mean)).
    The axial gradient term is used only when the nodes are spread over more than 0.5 mm in z; otherwise the
    coefficients belong to the mean z of the nodes (z_eff, relative to the requested plane)."""
    mean = sum(s[1] for s in samples) / float(len(samples))
    spread = max(abs(s[1] - mean) for s in samples)
    use_dz = spread > 0.5
    k = 4 if use_dz else 3
    A = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for th, dz, v in samples:
        row = [1.0, math.cos(th), math.sin(th)] + ([dz - mean] if use_dz else [])
        for i in range(k):
            b[i] += row[i] * v
            for j in range(k):
                A[i][j] += row[i] * row[j]
    x = _solve(A, b)
    if x is None:
        return [float("nan")] * 3, mean
    if use_dz:
        x[0] -= x[3] * mean          # value at the requested plane
        return x[:3], 0.0
    return x[:3], mean


PLANE_HEADER = "offset_mm,ring,step,nodes,band_mm,sz_c0,sz_c1,sz_s1,tzt_c0,tzt_c1,tzt_s1,z_eff_mm"


def plane_check(analysis, cs, frame, offsets, times, r_out, r_in, tag, pts=None):
    """Evaluates SZ, SXZ, SYZ (local) on the rings and returns csv rows."""
    out("")
    out("== Section-plane stresses (outer and inner surface rings) ==")
    if pts is None:
        pts = mesh_nodes_local(analysis, frame)
        resolve_weld_z(pts)
    out("mesh nodes: {0}, local z from {1:.2f} to {2:.2f} mm".format(len(pts), pts[0][1][2], pts[-1][1][2]))
    planes, notes = pick_planes(pts, offsets, r_out, r_in)
    for n in notes:
        out("  " + n)
    if not planes:
        out("No usable plane: the coordinate system origin must lie on the pipe axis (rings at r = R_OUT_MM / R_IN_MM).")
        return [], pts
    ids = sorted(set(n for _, _, res in planes for _, ring in res for _, n, _ in ring))
    out("planes used: {0}; nodes evaluated: {1}".format(", ".join("{0:+g}".format(p[0]) for p in planes), len(ids)))
    loc = node_location(ids)
    sol = analysis.Solution
    comps = ("SZ", "SXZ", "SYZ") if cs is not None else ("SX", "SY", "SZ", "SXY", "SYZ", "SXZ")
    results = [user_result(sol, e, loc, cs, "CHK_" + e + "_" + tag) for e in comps]
    rows = []
    try:
        for si, t in enumerate(times):
            vals = [evaluate(r, t) for r in results]
            if cs is not None:
                sz, sxz, syz = vals
            else:
                sz, sxz, syz = rotate_to_frame(vals, frame[1])
            for off, band, res in planes:
                for name, ring in res:
                    a, b = [], []
                    for th, n, dz in ring:
                        if n not in sz:
                            continue
                        a.append((th, dz, sz[n]))
                        b.append((th, dz, -sxz[n] * math.sin(th) + syz[n] * math.cos(th)))
                    if len(a) < 12:
                        continue
                    (cz, zeff), (ct, _) = fourier_fit(a), fourier_fit(b)
                    rows.append("{0:g},{1},{2},{3},{4:g},{5},{6:.3f}".format(
                        off, name, si + 1, len(a), band, ",".join("{0:.6g}".format(x) for x in cz + ct), off + zeff))
            out("  step {0} evaluated".format(si + 1))
    finally:
        if not KEEP_CHECK_RESULTS:
            for r in results:
                try:
                    r.Delete()
                except Exception:
                    pass
    return rows, pts


def rotate_to_frame(vals, axes):
    """Global SX, SY, SZ, SXY, SYZ, SXZ dicts -> local SZ, SXZ, SYZ dicts (axes = local unit vectors in global)."""
    sx, sy, sz, sxy, syz, sxz = vals
    ax, ay, az = axes
    rz, rxz, ryz = {}, {}, {}
    for n in sz:
        T = [[sx[n], sxy[n], sxz[n]], [sxy[n], sy[n], syz[n]], [sxz[n], syz[n], sz[n]]]
        Tz = [sum(T[i][j] * az[j] for j in range(3)) for i in range(3)]
        rz[n] = sum(az[i] * Tz[i] for i in range(3))
        rxz[n] = sum(ax[i] * Tz[i] for i in range(3))
        ryz[n] = sum(ay[i] * Tz[i] for i in range(3))
    return rz, rxz, ryz


def save_planes(path, label, rows):
    write_text(path, "# " + label + "\n" + PLANE_HEADER + "\n" + "\n".join(rows) + "\n")
    out("plane data: " + path)


def load_planes(path):
    data = {}
    for line in read_lines(path):
        if line.startswith("#") or line.startswith("offset"):
            continue
        p = line.split(",")
        key = (p[1], int(p[2]))
        z = float(p[11]) if len(p) > 11 and p[11].strip() else float(p[0])
        data.setdefault(key, []).append((z, [float(x) for x in p[5:11]]))
    for k in data:
        data[k].sort()
    return data


def _interp(lst, off, max_gap=80.0):
    """Linear interpolation of parent coefficients at offset off (same side of the weld only)."""
    same = [x for x in lst if x[0] * off > 0]
    for i in range(len(same)):
        if abs(same[i][0] - off) < 1e-6:
            return same[i][1]
    for i in range(len(same) - 1):
        a, b = same[i], same[i + 1]
        if a[0] <= off <= b[0] and b[0] - a[0] <= max_gap:
            w = (off - a[0]) / (b[0] - a[0])
            return [a[1][k] * (1 - w) + b[1][k] * w for k in range(6)]
    return None


def _amp(c):
    return abs(c[0]) + (c[1] ** 2 + c[2] ** 2) ** 0.5


def compare_planes(child_rows, parent_path, parent_label, limit_ok=0.02, limit_warn=0.05):
    out("")
    out("== Comparison with " + parent_label + " ==")
    if not File.Exists(parent_path):
        out("Parent file not found: " + parent_path)
        out("Run the parent model check first (it writes this file), then run this script again.")
        return
    parent = load_planes(parent_path)
    child = {}
    for line in child_rows:
        p = line.split(",")
        z = float(p[11]) if len(p) > 11 else float(p[0])
        child.setdefault(float(p[0]), []).append((p[1], int(p[2]), [float(x) for x in p[5:11]], z))
    # reference amplitude of each step: median response of the parent over its planes (avoids dividing by ~0)
    amps = {}
    for (ring, step), lst in parent.items():
        for _, c in lst:
            amps.setdefault(step, []).append(max(_amp(c[:3]), _amp(c[3:])))
    ref = dict((k, sorted(v)[len(v) // 2]) for k, v in amps.items())
    out("difference = max over theta of |stress(child) - stress(parent)| / largest stress amplitude of the step (parent)")
    out("offset_mm   worst_step   max_diff   verdict")
    worst_all = 0.0
    for off in sorted(child):
        worst, wstep = -1.0, 0
        for ring, step, c, z in child[off]:
            pc = _interp(parent.get((ring, step), []), z)
            if pc is None:
                continue
            ps, pt = pc[:3], pc[3:]
            amp = max(_amp(ps), _amp(pt), 0.05 * ref.get(step, 0.0), 1e-30)
            d_s = abs(c[0] - ps[0]) + ((c[1] - ps[1]) ** 2 + (c[2] - ps[2]) ** 2) ** 0.5
            d_t = abs(c[3] - pt[0]) + ((c[4] - pt[1]) ** 2 + (c[5] - pt[2]) ** 2) ** 0.5
            e = max(d_s, d_t) / amp
            if e > worst:
                worst, wstep = e, step
        if worst < 0:
            out("{0:+9.1f}   (parent has no data at this position)".format(off))
            continue
        verdict = "OK" if worst <= limit_ok else ("ACCEPTABLE" if worst <= limit_warn else "CHECK")
        out("{0:+9.1f}   {1:10d}   {2:8.2%}   {3}".format(off, wstep, worst, verdict))
        worst_all = max(worst_all, worst)
    out("Criterion: <= {0:.0%} OK, <= {1:.0%} acceptable, larger: check cut boundary / step mapping / coordinate system."
        .format(limit_ok, limit_warn))
    offs = [o for o in sorted(child) if any(_interp(parent.get((r, s), []), z) is not None for r, s, _, z in child[o])]
    if offs:
        out("")
        out("Detail at the compared planes nearest to the cut faces (child / parent, MPa per unit load):")
        out("   plane  step  ring     axial-mean SZ        bending |SZ|         torsion TZT          diff of the main term")
        names = {1: "axial", 2: "shear", 4: "torsion", 5: "bending"}
        dead = {}
        for o in sorted(set([offs[0], offs[-1]])):
            for ring, step, c, z in sorted(child[o], key=lambda t: (t[1], t[0])):
                if step not in names:
                    continue
                pc = _interp(parent.get((ring, step), []), z)
                if pc is None:
                    continue
                bc, bp = (c[1] ** 2 + c[2] ** 2) ** 0.5, (pc[1] ** 2 + pc[2] ** 2) ** 0.5
                main = {1: (c[0], pc[0]), 2: (bc, bp), 4: (c[3], pc[3]), 5: (bc, bp)}[step]
                d = (main[0] - main[1]) / max(abs(main[1]), 1e-30)
                if abs(main[1]) > 1e-12:
                    dead.setdefault(o, []).append(abs(main[0]) / abs(main[1]))
                out("  {0:+6.1f}  {1:4d}  {2:6s}  {3:8.4f} / {4:8.4f}  {5:8.4f} / {6:8.4f}  {7:8.4f} / {8:8.4f}  {9:+7.2%} ({10})".format(
                    o, step, ring, c[0], pc[0], bc, bp, c[3], pc[3], d, names[step]))
        out("Bending differences of opposite sign on the outer and inner ring = local through-thickness bending that the")
        out("parent does not have (different weld geometry near the cut, or too few elements through the wall in the")
        out("parent). The same difference on both rings = load / boundary transfer error.")
        for o, r in sorted(dead.items()):
            if r and max(r) < 0.2:
                out("[ERROR]   plane {0:+g} mm: stresses are almost zero in every step (largest child/parent = {1:.0%})."
                    .format(o, max(r)))
                out("          The cut face on this side receives no displacement: it is missing from the Geometry of the")
                out("          Imported Cut Boundary Constraint, or its nodes were not mapped from the parent. Select BOTH")
                out("          cut faces, re-import, solve again and rerun this script before exporting (04-07).")
            elif r and min(r) < 0.5:
                out("[CHECK]   plane {0:+g} mm: some steps carry less than half of the parent stress ({1:.0%}).".format(o, min(r)))
                out("          Check the Imported Cut Boundary Constraint on this cut face and the source time mapping.")
    return worst_all


def save_log(folder, name):
    path = Path.Combine(folder, name + "_" + now_tag() + ".txt")
    write_text(path, "\n".join(LOG) + "\n")
    print("Report: " + path)


SKIP_WORDS = ("AnalysisSettings", "Solution", "Initial", "Comment", "Figure", "Image", "Result", "Probe",
              "Reaction", "Stress", "Deformation", "Strain", "Chart", "Commands", "Command")


def submodel_tree_check(analysis):
    """Submodel: only the imported cut boundary constraint may load the model."""
    out("")
    out("== Boundary conditions of the submodel ==")
    cut, extra = [], []
    for obj in list(analysis.Children):
        cat = category(obj)
        if get(obj, "Suppressed", False) is True:
            continue
        if "Submodel" in cat or "Imported" in cat or "Cut" in cat:
            cut.append(obj)
            for ch in walk(obj):
                if "Cut" in category(ch) or "Imported" in category(ch):
                    cut.append(ch)
            continue
        if any(w in cat for w in SKIP_WORDS):
            continue
        extra.append("{0} ({1})".format(obj.Name, cat))
    names = ", ".join("{0} ({1})".format(o.Name, category(o)) for o in cut)
    check(len(cut) >= 1, "Imported Cut Boundary Constraint present: {0}".format(names or "none"))
    check(not extra, "no other loads or supports: {0}".format(", ".join(extra) or "none"))
    out("Check by eye in the Imported Cut Boundary Constraint worksheet: source time 1..12 s -> analysis time 1..12 s.")
    return cut


def fat_z_range(analysis, frame, name="FAT", absolute=False):
    """Axial range of the FAT fillet faces (offset from the weld, or absolute z), or None."""
    try:
        sel = list(ExtAPI.DataModel.GetObjectsByName(name))[0]
        mesh = analysis.MeshData
        f = factor_to_mm(str(mesh.Unit))
        zs = []
        for fid in list(sel.Location.Ids):
            for n in mesh.MeshRegionById(int(fid)).NodeIds:
                nd = mesh.NodeById(int(n))
                zs.append(to_local([float(nd.X) * f, float(nd.Y) * f, float(nd.Z) * f], frame)[2] - (0.0 if absolute else WELD_Z_MM))
        return min(zs), max(zs)
    except Exception:
        return None


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
