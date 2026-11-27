# -*- coding: utf-8 -*-
# Pure ASCII file on purpose: runs in Mechanical IronPython 2.7 and CPython.
"""
06  SECOND SUBMODEL - export the shape of the weld (meridional cuts of the mesh)
    (needs only the mesh, can be run before or after solving; read-only)

The software rebuilds the weld in 3D from this file: pipe, cap, root, toe fillets and the cut faces.
It also checks the weld geometry: cap height and width, flank angle, root, wall thickness and hi-lo
misalignment, by comparing the cuts at 0, 90, 180 and 270 degrees.

Writes into Desktop/FAT_ANSYS (same folder as scripts 04/05):
  weld_profile_nodes.csv   nodes of the mesh lying in the four meridional half-planes:
                           cut_deg, node_id, z_rel_mm (relative to the weld plane), r_mm, theta_deg
  weld_profile_faces.csv   element faces lying in these half-planes (2D mesh of each cut):
                           cut_deg, n1, n2, n3, n4 (n4 = -1 for triangles)
  07_weld_profile_<time>.txt  summary: extents, wall thickness, cap / root height per cut
Size: a few thousand rows (about 0.5 MB). Run time: 2-5 min (one pass over the nodes, like script 03).
"""
ANALYSIS_INDEX = 0
COORDINATE_SYSTEM_NAME = "local"   # pipe system: z along the axis
WELD_Z_MM = None                   # None = automatic (middle of the model); or z of the weld in mm
CUTS_DEG = [0.0, 90.0, 180.0, 270.0]
R_OUT_MM = 147.0
R_IN_MM = 127.0
FAT_SELECTION = "FAT"
KEEP_CHECK_RESULTS = False

#@COMMON@


def angle_diff(a, b):
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d)


def polar_nodes(pts):
    res = []
    for n, p in pts:
        r = (p[0] ** 2 + p[1] ** 2) ** 0.5
        if r > 1e-6:
            res.append((n, p[2] - WELD_Z_MM, r, math.degrees(math.atan2(p[1], p[0]))))
    return res


def slice_nodes(polar, cut):
    """Nodes in the half-plane theta = cut (tolerance grows until the layer is found)."""
    tol = 0.02
    while tol <= 1.0:
        sel = [q for q in polar if angle_diff(q[3], cut) <= tol]
        if len(sel) >= 200:
            return sel, tol
        tol *= 2.0
    return sel, tol


def slice_faces(mesh, ids):
    """Element faces whose corner nodes all lie in the slice (quads of hexes, triangles of wedges / tets)."""
    inside = set(ids)
    faces, seen = [], set()
    elems = set()
    try:
        for n in ids:
            for e in mesh.NodeById(n).ConnectedElementIds:
                elems.add(int(e))
    except Exception:
        return None
    for e in elems:
        el = mesh.ElementById(e)
        try:
            corner = [int(x) for x in el.CornerNodeIds]
        except Exception:
            corner = [int(x) for x in el.NodeIds][:8]
        f = [x for x in corner if x in inside]
        if len(f) in (3, 4):
            key = tuple(sorted(f))
            if key not in seen:
                seen.add(key)
                faces.append(f)
    return faces


def main():
    model = ExtAPI.DataModel.Project.Model
    analysis = model.Analyses[ANALYSIS_INDEX]
    folder = desktop_folder(OUTPUT_FOLDER)
    out("06 weld profile export   analysis: {0}   {1}".format(analysis.Name, now_tag()))
    cs, frame = get_frame(model, COORDINATE_SYSTEM_NAME)
    pts = mesh_nodes_local(analysis, frame)
    resolve_weld_z(pts, fat_z_range(analysis, frame, FAT_SELECTION, absolute=True))
    zlo, zhi = pts[0][1][2] - WELD_Z_MM, pts[-1][1][2] - WELD_Z_MM
    out("mesh nodes: {0}; model extent relative to the weld: {1:+.2f} ... {2:+.2f} mm".format(len(pts), zlo, zhi))
    mesh = analysis.MeshData
    node_rows, face_rows = [], []
    out("")
    out("cut_deg  nodes  tol_deg  faces  r_min    r_max    wall_far  cap_height  root_height  (mm)")
    polar = polar_nodes(pts)
    for cut in CUTS_DEG:
        sel, tol = slice_nodes(polar, cut)
        for n, z, r, th in sel:
            node_rows.append("{0:g},{1},{2:.4f},{3:.4f},{4:.4f}".format(cut, n, z, r, th))
        faces = slice_faces(mesh, [s[0] for s in sel])
        if faces is not None:
            for f in faces:
                face_rows.append("{0:g},{1}".format(cut, ",".join(str(x) for x in (f + [-1])[:4])))
        if not sel:
            out("{0:7g}  no nodes found".format(cut))
            continue
        rs = [s[2] for s in sel]
        far = [s for s in sel if abs(s[1]) > 0.8 * max(abs(zlo), abs(zhi))]
        wall = (max(s[2] for s in far) - min(s[2] for s in far)) if far else float("nan")
        mid = [s for s in sel if abs(s[1]) < 2.0]
        cap = (max(s[2] for s in mid) - R_OUT_MM) if mid else float("nan")
        root = (R_IN_MM - min(s[2] for s in mid)) if mid else float("nan")
        out("{0:7g}  {1:5d}  {2:7.3f}  {3:5s}  {4:7.3f}  {5:7.3f}  {6:8.3f}  {7:10.3f}  {8:11.3f}".format(
            cut, len(sel), tol, str(len(faces)) if faces is not None else "-", min(rs), max(rs), wall, cap, root))
    write_text(Path.Combine(folder, "weld_profile_nodes.csv"),
               "cut_deg,node_id,z_rel_mm,r_mm,theta_deg\n" + "\n".join(node_rows) + "\n")
    out("")
    out("nodes: " + Path.Combine(folder, "weld_profile_nodes.csv") + "  ({0} rows)".format(len(node_rows)))
    if face_rows:
        write_text(Path.Combine(folder, "weld_profile_faces.csv"), "cut_deg,n1,n2,n3,n4\n" + "\n".join(face_rows) + "\n")
        out("faces: " + Path.Combine(folder, "weld_profile_faces.csv") + "  ({0} rows)".format(len(face_rows)))
    else:
        out("element faces not available in this version; the software uses the outline of the nodes instead")
    out("cap_height / root_height: highest point of the cap above R_OUT and of the root below R_IN within +/-2 mm of the weld.")
    out("Different values between the cuts mean the weld is not axisymmetric (misalignment or a varying cap).")
    save_log(folder, "07_weld_profile")


with quiet():
    main()
