import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import 'api.dart';
import 'location.dart';
import 'photo_view.dart';
import 'species_label.dart';

/// Where the map opens if the device location is unavailable: District 1, Ho Chi Minh City.
const _fallbackCenter = LatLng(10.7769, 106.7009);

Future<LatLng> _deviceLocation() async {
  final p = await currentPosition();
  return LatLng(p.latitude, p.longitude);
}

class MapScreen extends StatefulWidget {
  const MapScreen({super.key, required this.api, this.locate = _deviceLocation});

  final ApiClient api;
  final Future<LatLng> Function() locate;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final _map = MapController();
  LatLng? _start;
  List<Zone> _zones = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _findStart();
  }

  Future<void> _findStart() async {
    LatLng start;
    try {
      start = await widget.locate();
    } catch (_) {
      start = _fallbackCenter;
    }
    if (mounted) setState(() => _start = start);
  }

  Future<void> _load(MapCamera camera) async {
    // Radius from the centre to the farthest visible corner.
    final radius = const Distance().as(LengthUnit.Meter, camera.center, camera.visibleBounds.northEast);
    try {
      final zones = await widget.api.zones(
        latitude: camera.center.latitude,
        longitude: camera.center.longitude,
        radiusMeters: max(radius, 500),
      );
      if (mounted) {
        setState(() {
          _zones = zones;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = 'Could not load the map: $e');
    }
  }

  void _openZone(Zone zone) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (_) => _ZoneSheet(api: widget.api, zone: zone),
    );
  }

  @override
  Widget build(BuildContext context) {
    final start = _start;
    if (start == null) return const Center(child: CircularProgressIndicator());

    final color = Theme.of(context).colorScheme.primary;
    return Stack(
      children: [
        FlutterMap(
          mapController: _map,
          options: MapOptions(
            initialCenter: start,
            initialZoom: 15,
            minZoom: 11,
            onMapReady: () => _load(_map.camera),
            onMapEvent: (event) {
              if (event is MapEventMoveEnd || event is MapEventFlingAnimationEnd) {
                _load(event.camera);
              }
            },
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'app.pawdex.pawdex',
            ),
            PolygonLayer(
              polygons: [
                for (final z in _zones)
                  Polygon(
                    points: [for (final (lat, lon) in z.boundary) LatLng(lat, lon)],
                    color: color.withValues(alpha: 0.18),
                    borderColor: color,
                    borderStrokeWidth: 1.5,
                  ),
              ],
            ),
            MarkerLayer(
              markers: [
                for (final z in _zones)
                  Marker(
                    point: LatLng(z.center.$1, z.center.$2),
                    width: 90,
                    height: 36,
                    child: _ZoneBadge(zone: z, onTap: () => _openZone(z)),
                  ),
              ],
            ),
            const RichAttributionWidget(
              attributions: [TextSourceAttribution('OpenStreetMap contributors')],
            ),
          ],
        ),
        if (_error != null)
          Positioned(
            left: 12,
            right: 12,
            top: 12,
            child: Card(child: Padding(padding: const EdgeInsets.all(12), child: Text(_error!))),
          ),
      ],
    );
  }
}

class _ZoneBadge extends StatelessWidget {
  const _ZoneBadge({required this.zone, required this.onTap});

  final Zone zone;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final parts = [
      if (zone.cats > 0) '🐱${zone.cats}',
      if (zone.dogs > 0) '🐶${zone.dogs}',
    ];
    return Center(
      child: Material(
        elevation: 2,
        shape: const StadiumBorder(),
        color: Theme.of(context).colorScheme.surface,
        child: InkWell(
          customBorder: const StadiumBorder(),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            child: Text(parts.join(' '), style: const TextStyle(fontWeight: FontWeight.bold)),
          ),
        ),
      ),
    );
  }
}

/// "Who lives here?"
class _ZoneSheet extends StatefulWidget {
  const _ZoneSheet({required this.api, required this.zone});

  final ApiClient api;
  final Zone zone;

  @override
  State<_ZoneSheet> createState() => _ZoneSheetState();
}

class _ZoneSheetState extends State<_ZoneSheet> {
  late final Future<List<Animal>> _animals = widget.api.zoneAnimals(widget.zone.cell);

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Animal>>(
      future: _animals,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Padding(padding: const EdgeInsets.all(24), child: Text('${snapshot.error}'));
        }
        if (!snapshot.hasData) {
          return const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()));
        }
        final animals = snapshot.data!;
        return ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text('Who lives here', style: Theme.of(context).textTheme.titleLarge),
            ),
            for (final a in animals)
              ListTile(
                leading: ApiPhoto(load: () => widget.api.animalPhoto(a.id), size: 56),
                title: Text(animalTitle(a.name, a.species)),
                subtitle: Text('${speciesLabel(a.species)} · seen ${a.sightingsCount} '
                    '${a.sightingsCount == 1 ? 'time' : 'times'}'),
              ),
          ],
        );
      },
    );
  }
}
