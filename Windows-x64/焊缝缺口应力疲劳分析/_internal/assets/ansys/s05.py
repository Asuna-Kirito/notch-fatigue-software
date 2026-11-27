# -*- coding: utf-8 -*-
# Pure ASCII file on purpose: runs in Mechanical IronPython 2.7 and CPython.
"""
05  SECOND SUBMODEL - export node coordinates and the surface mesh of the FAT faces
    (needs only the mesh, can be run before or after solving)

Writes into Desktop/FAT_ANSYS (same folder as script 04):
  nodes_xyz.csv        node coordinates (mm): local and global, face id, body id
  surface_facets.csv   surface facets on FAT (3D display in the software)
  mesh_quality.csv     size of every FAT surface element: arc / circumferential / depth (mm), aspect ratio
  export_info_mesh.txt element types, size statistics (median / 95 % / max)
The software reads these files together with the STEP files of script 04.
"""
SELECTION_NAME = "FAT"                    # or ["FAT1", "FAT2"]
COORDINATE_SYSTEM_NAME = "local"   # pipe system: z along the axis; first submodel without it uses the saved full-model local
WELD_Z_MM = None                   # None = automatic (middle of the model); or z of the weld in mm
ANALYSIS_INDEX = 0
KEEP_CHECK_RESULTS = False

#@COMMON@


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def centroid(pts):
    n = float(len(pts))
    return [sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n]


def stats(values):
    v = sorted(values)
    if not v:
        return {}
    return {"min": v[0], "median": v[len(v) // 2], "p95": v[int(0.95 * (len(v) - 1))], "max": v[-1]}


def export_geometry(analysis, selections, frame, out_dir, info):
    mesh = analysis.MeshData
    unit = str(mesh.Unit)
    f = factor_to_mm(unit)
    info["mesh_length_unit"] = unit
    cache = {}

    def xyz(n):
        if n not in cache:
            nd = mesh.NodeById(n)
            g = [float(nd.X) * f, float(nd.Y) * f, float(nd.Z) * f]
            loc = to_local(g, frame) if frame else list(g)
            loc[2] = loc[2] - WELD_Z_MM + REF_WELD_Z_MM      # full-model convention: weld at z = 13000
            cache[n] = (loc, g)
        return cache[n]

    node_face, facets, quality = {}, [], []
    elem_types = {}
    face_ids = []
    for selection in selections:
        face_ids.extend(list(selection.Location.Ids))
    for fid in face_ids:
        region = mesh.MeshRegionById(int(fid))
        nset = set(int(n) for n in region.NodeIds)
        for n in nset:
            node_face.setdefault(n, int(fid))
        for eid in region.ElementIds:
            e = mesh.ElementById(int(eid))
            try:
                et = str(e.Type)
            except Exception:
                et = "unknown"
            elem_types[et] = elem_types.get(et, 0) + 1
            corner = [int(n) for n in e.CornerNodeIds]
            on_face = [n for n in corner if n in nset]
            if len(on_face) < 3:
                continue
            facets.append((int(fid), int(eid), on_face[:4]))
            # element size: edges of the surface facet classified by direction, depth = facet -> opposite corners
            p = [xyz(n)[0] for n in on_face]
            others = [xyz(n)[0] for n in corner if n not in on_face]
            pairs = []
            for i in range(len(p)):
                for j in range(i + 1, len(p)):
                    pairs.append((dist(p[i], p[j]), i, j))
            pairs.sort()
            sides = pairs[:4] if len(p) == 4 else pairs[:3]
            arc, circ = [], []
            for L, i, j in sides:
                dz = abs(p[i][2] - p[j][2])
                (arc if L > 0 and dz / L > 0.5 else circ).append(L)
            depth = dist(centroid(p), centroid(others)) if others else 0.0
            a = max(arc) if arc else 0.0
            c = max(circ) if circ else 0.0
            dims = [x for x in (a, c, depth) if x > 0]
            aspect = max(dims) / min(dims) if dims else 0.0
            quality.append((int(fid), int(eid), a, c, depth, aspect))
    face_body = {}
    for fid in set(node_face.values()):
        try:
            ent = ExtAPI.DataModel.GeoData.GeoEntityById(fid)
            face_body[fid] = int(list(ent.Bodies)[0].Id)
        except Exception:
            face_body[fid] = -1
    w = StreamWriter(Path.Combine(out_dir, "nodes_xyz.csv"), False, UTF8Encoding(True))
    zs = []
    try:
        w.Write("node_id,face_id,body_geo_id,x_local_mm,y_local_mm,z_local_mm,x_global_mm,y_global_mm,z_global_mm\n")
        for n in sorted(node_face):
            loc, g = xyz(n)
            if not frame:
                loc = [float("nan")] * 3
            zs.append(loc[2] if frame else g[2])
            w.Write("{0},{1},{2},{3}\n".format(n, node_face[n], face_body[node_face[n]],
                                              ",".join(format(v, ".10g") for v in loc + g)))
    finally:
        w.Close()
    w = StreamWriter(Path.Combine(out_dir, "surface_facets.csv"), False, UTF8Encoding(True))
    try:
        w.Write("face_id,element_id,n1,n2,n3,n4\n")
        for fid, eid, ns in facets:
            ns = ns + [-1] * (4 - len(ns))
            w.Write("{0},{1},{2}\n".format(fid, eid, ",".join(str(x) for x in ns)))
    finally:
        w.Close()
    w = StreamWriter(Path.Combine(out_dir, "mesh_quality.csv"), False, UTF8Encoding(True))
    try:
        w.Write("face_id,element_id,arc_mm,circumferential_mm,depth_mm,aspect_ratio\n")
        for q in quality:
            w.Write("{0},{1},{2:.5g},{3:.5g},{4:.5g},{5:.4g}\n".format(*q))
    finally:
        w.Close()
    info["geometry_nodes"] = len(node_face)
    info["geometry_facets"] = len(facets)
    info["element_types_on_FAT"] = ", ".join("{0}:{1}".format(k, v) for k, v in sorted(elem_types.items()))
    info["mesh_arc_mm"] = stats([q[2] for q in quality if q[2] > 0])
    info["mesh_circumferential_mm"] = stats([q[3] for q in quality if q[3] > 0])
    info["mesh_depth_first_layer_mm"] = stats([q[4] for q in quality if q[4] > 0])
    info["mesh_aspect_ratio"] = stats([q[5] for q in quality if q[5] > 0])
    if zs:
        info["node_z_min_mm"] = min(zs)
        info["node_z_max_mm"] = max(zs)
        if frame and not (REF_WELD_Z_MM - 60. < min(zs) and max(zs) < REF_WELD_Z_MM + 60.):
            msg = ("FAT nodes are not near z = WELD_Z_MM in '{0}' (z from {1:.1f} to {2:.1f} mm); "
                   "check the coordinate system".format(COORDINATE_SYSTEM_NAME, min(zs), max(zs)))
            info["warning_coordinates"] = msg
            ExtAPI.Log.WriteMessage("ENS WARNING: " + msg)


def main():
    model = ExtAPI.DataModel.Project.Model
    analysis = model.Analyses[ANALYSIS_INDEX]
    matches = get_selections(SELECTION_NAME)
    cs = find_coordinate_system(model, COORDINATE_SYSTEM_NAME)
    frame = coordinate_frame(cs)
    check_against_saved(frame)
    resolve_weld_z(mesh_nodes_local(analysis, frame), fat_z_range(analysis, frame, SELECTION_NAME, absolute=True))
    folder = desktop_folder(OUTPUT_FOLDER)
    info = {}
    export_geometry(analysis, matches, frame, folder, info)
    lines = ["exported = " + now_tag(), "coordinate_system = " + COORDINATE_SYSTEM_NAME]
    for k in sorted(info):
        v = info[k]
        if isinstance(v, dict):
            v = ", ".join("{0} {1:.4g}".format(a, v[a]) for a in ("min", "median", "p95", "max") if a in v)
        lines.append("{0} = {1}".format(k, v))
    write_text(Path.Combine(folder, "export_info_mesh.txt"), "\n".join(lines) + "\n")
    for line in lines:
        out(line)
    out("")
    out("Targets for SOLID185 at a 1 mm fillet: arc <= 0.17 mm, first layer (depth) 0.05-0.08 mm,")
    out("circumferential <= 1.3 mm, aspect ratio <= 20 (report 01, table 11-2).")
    out("EXPORT COMPLETE: " + folder)


with quiet():
    main()
