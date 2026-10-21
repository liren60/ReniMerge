# -*- coding: utf-8 -*-
"""
ReniMerge — merge component geometry in Visual Components 5.1 (Python 3).

Copyright (c) 2026 Reni / liren
All rights reserved.

Author: Reni (liren)
Product: Reni Tools for Visual Components
"""

import math

import vcCore as vc
import vcFeatures as vc_fea
import vcGeometry as vc_geo

__author__ = 'Reni / liren'
__copyright__ = 'Copyright (c) 2026 Reni / liren'
__version__ = '1.0.0'

app = vc.getApplication()
cmd = vc.getCommand()
sel = app.SelectionManager
loc = app.LocalizationService

CMD_ID = 'ReniMerge'
PLACE_KEEP = 'KeepWorldPlacement'
PLACE_ORIGIN = 'PlaceAtTargetOrigin'
EMPTY_TARGET = 'NoSelection'

_active = False
_events = False
_busy = False
_guides = []


def _t(key, fallback=None):
    value = loc.getLocalizedString(key)
    if not value or value == key:
        return fallback if fallback is not None else key
    return value


def _k(*parts):
    return 'ComboKey::Python.%s.%s' % (CMD_ID, '.'.join(parts))


def OnInit():
    cmd.Name = CMD_ID
    cmd.addMenuItem('VcConfigure3DContextMenu', CMD_ID, position=-1)
    cmd.addMenuItem('VcTabHome/Python3', CMD_ID, position=-1)


def OnExecute():
    global _active, _events
    _active = True
    if not _events:
        sel.OnSelectionChanged += _on_selection
        _events = True
    panel.Title = _t(_k('Text'), 'Reni Merge')
    panel.showCommand(cmd)
    _on_selection()


def _apply():
    if _run_merge():
        _shutdown()
        return True
    return False


def _close():
    _shutdown()
    return True


def _cancel():
    _shutdown()


def _shutdown():
    global _active
    _active = False
    _clear_guides()
    app.render()


def _on_selection(*_args):
    if _active:
        _sync_targets()


def _on_prop(*_args):
    if _active and not _busy:
        _draw_guides()


def _picked():
    return list(sel.getSelection(vc.vcComponent))


def _sync_targets():
    global _busy
    names = [c.Name for c in _picked()]
    _busy = True
    try:
        if names:
            target_prop.AllowedValues = names
            if target_prop.Value not in names:
                target_prop.Value = names[-1]
        else:
            target_prop.AllowedValues = [EMPTY_TARGET]
            target_prop.Value = EMPTY_TARGET
    finally:
        _busy = False
    _draw_guides()


def _world():
    return app.WorldManager.ActiveWorld


def _clear_guides():
    while _guides:
        geo = _guides.pop()
        geo.delete()


def _node_center_mtx(node):
    mtx = node.WorldPositionMatrix
    center = node.BoundingBox.Center
    mtx.translateRel(center.X, center.Y, center.Z)
    return mtx


def _append_box(node, lines):
    half = node.BoundingBox.HalfDiagonal
    hx, hy, hz = half.X * 1.02, half.Y * 1.02, half.Z * 1.02
    mtx = _node_center_mtx(node)
    mtx.translateRel(hx, hy, hz)
    a = mtx.P
    mtx.translateRel(0, -hy * 2, 0)
    b = mtx.P
    mtx.translateRel(-hx * 2, 0, 0)
    c = mtx.P
    mtx.translateRel(0, hy * 2, 0)
    d = mtx.P
    mtx.translateRel(hx * 2, 0, -hz * 2)
    e = mtx.P
    mtx.translateRel(0, -hy * 2, 0)
    f = mtx.P
    mtx.translateRel(-hx * 2, 0, 0)
    g = mtx.P
    mtx.translateRel(0, hy * 2, 0)
    h = mtx.P
    lines.addLine([a, b, c, d, a])
    lines.addLine([e, f, g, h, e])
    lines.addLine([a, e])
    lines.addLine([b, f])
    lines.addLine([c, g])
    lines.addLine([d, h])


def _arc(p0, p1):
    pts = [p0]
    span = (p1 - p0).length()
    steps = 20
    for i in range(steps):
        t = float(i + 1) / float(steps + 1)
        p = p0 * (1.0 - t) + p1 * t
        p.Z = p.Z + math.sin(t * math.pi) * span * 0.1
        pts.append(p)
    pts.append(p1)
    return pts


def _draw_guides():
    _clear_guides()
    name = target_prop.Value
    if not name or name == EMPTY_TARGET:
        app.render()
        return
    world = _world()
    target = world.findComponent(name)
    if target is None:
        app.render()
        return

    mat = app.findMaterial('green')
    container = world.UserGeometry
    box = container.createGeometrySet(vc_geo.vcGeometrySetType.LINE_SET)
    box.LineWidth = 3
    if mat is not None:
        box.Material = mat
    _append_box(target, box)
    box.update()
    _guides.append(box)

    c0 = _node_center_mtx(target).P
    links = container.createGeometrySet(vc_geo.vcGeometrySetType.LINE_SET)
    links.LineWidth = 2
    if mat is not None:
        links.Material = mat
    for other_name in target_prop.AllowedValues:
        if other_name in (name, EMPTY_TARGET):
            continue
        other = world.findComponent(other_name)
        if other is None:
            continue
        links.addLine(_arc(c0, _node_center_mtx(other).P))
    links.update()
    _guides.append(links)
    app.render()


def _walk_nodes(comp):
    queue = [comp]
    out = []
    while queue:
        node = queue.pop(0)
        out.append(node)
        queue.extend([ch for ch in node.Children if ch.Component == comp])
    return out


def _offset(target, source, node, keep_world):
    if keep_world:
        return target.InverseWorldPositionMatrix * node.WorldPositionMatrix
    if node is not source:
        return source.InverseWorldPositionMatrix * node.WorldPositionMatrix
    return vc.vcMatrix.new()


def _new_geo_feature(comp, base):
    label = base or 'reni_geo'
    n = 2
    while comp.findFeature(label) is not None:
        label = '%s_%d' % (base, n)
        n += 1
    return comp.RootFeature.create(vc_fea.vcFeatureType.GEOMETRY, label)


def _run_merge():
    _clear_guides()
    world = _world()
    target_name = target_prop.Value
    target = world.findComponent(target_name) if target_name and target_name != EMPTY_TARGET else None
    if target is None:
        print(_t(_k('MsgNeedSelection'), 'Reni Merge: select at least two components.'))
        return False

    sources = []
    for name in list(target_prop.AllowedValues):
        if name in (target_name, EMPTY_TARGET):
            continue
        src = world.findComponent(name)
        if src is not None and src is not target:
            sources.append(src)
    if not sources:
        print(_t(_k('MsgNeedSelection'), 'Reni Merge: select at least two components.'))
        return False

    keep_world = placement_prop.Value == PLACE_KEEP
    keep_sources = bool(preserve_prop.Value)
    try:
        target.makeUnique()
        target.rebuild()
        for src in sources:
            src.makeUnique()
            src.rebuild()
            for node in _walk_nodes(src):
                if node is src:
                    feat_name = 'Reni_%s' % src.Name
                else:
                    feat_name = 'Reni_%s_%s' % (src.Name, node.Name)
                feature = _new_geo_feature(target, feat_name)
                node.rebuild()
                node.Geometry.cloneGeometrySets(
                    feature.Geometry,
                    offset=_offset(target, src, node, keep_world),
                )
                feature.rebuild()
            if not keep_sources:
                src.delete()
        target.rebuild()
    except Exception as err:
        print(_t(_k('MsgFailed'), 'Reni Merge failed: {0}').format(err))
        app.render()
        return False

    app.render()
    print(_t(_k('MsgDone'), 'Reni Merge: merged {0} into {1}.').format(len(sources), target.Name))
    return True


target_prop = cmd.Properties.create(vc.vcStepPropertyType.STRING, 'Target')
target_prop.AllowedValues = [EMPTY_TARGET]
target_prop.Value = EMPTY_TARGET
target_prop.OnChanged += _on_prop

placement_prop = cmd.Properties.create(vc.vcStepPropertyType.STRING, 'Placement')
placement_prop.AllowedValues = [PLACE_KEEP, PLACE_ORIGIN]
placement_prop.Value = PLACE_KEEP
placement_prop.OnChanged += _on_prop

preserve_prop = cmd.Properties.create(vc.vcPropertyType.BOOL, 'PreserveSources')
preserve_prop.Value = False

panel = vc.vcCommandPanel.new()
panel.Title = _t(_k('Text'), 'Reni Merge')
panel.setOnCancel(_cancel)

btn_ok = panel.createButton(_t('cmnBtnApply', 'Apply'), _apply)
btn_ok.IsEnabled = True
btn_close = panel.createButton(_t('cmnBtnClose', 'Close'), _close)
btn_close.IsEnabled = True
