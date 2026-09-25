import 'dart:typed_data';

import 'package:flutter/material.dart';

/// Shows photo bytes loaded by the API client (photos need the X-User-Id header,
/// so Image.network can't be used).
class ApiPhoto extends StatefulWidget {
  const ApiPhoto({super.key, required this.load, this.size, this.radius = 8});

  final Future<Uint8List> Function() load;
  final double? size;
  final double radius;

  @override
  State<ApiPhoto> createState() => _ApiPhotoState();
}

class _ApiPhotoState extends State<ApiPhoto> {
  late final Future<Uint8List> _bytes = widget.load();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(widget.radius),
        child: FutureBuilder<Uint8List>(
          future: _bytes,
          builder: (context, snapshot) => snapshot.hasData
              ? Image.memory(snapshot.data!, fit: BoxFit.cover)
              : const ColoredBox(color: Colors.black12),
        ),
      ),
    );
  }
}
