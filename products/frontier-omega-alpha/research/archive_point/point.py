"""Recover one point from a regular-grid GRIB2 5.3 prefix without decoding a grid."""
from datetime import datetime, timezone
from math import isfinite
import struct


def require(value, message):
    if not value:
        raise ValueError(message)


def unsigned(data, start, width):
    require(start >= 0 and start + width <= len(data), "INSUFFICIENT_FIELD_PREFIX")
    return int.from_bytes(data[start:start+width], "big")


def signed(data, start, width):
    value = unsigned(data, start, width)
    sign = 1 << (8 * width - 1)
    return -(value - sign) if value & sign else value


def bits(data, begin, width):
    if not width:
        return 0
    first = begin // 8
    past = (begin + width + 7) // 8
    field = unsigned(data, first, past - first)
    return (field >> (past*8 - begin - width)) & ((1 << width) - 1)


def ordered_grid(grid, latitude, longitude):
    require(len(grid) == 72 and unsigned(grid, 12, 2) == 0 and grid[71] == 0 and
            unsigned(grid, 38, 4) == 0, "UNSUPPORTED_GRID_OR_SCAN_ORDER")
    nx, ny = unsigned(grid, 30, 4), unsigned(grid, 34, 4)
    i_step, j_step = unsigned(grid, 63, 4), unsigned(grid, 67, 4)
    require((nx, ny, i_step, j_step) == (1440, 721, 250000, 250000), "UNAPPROVED_GRID_QUANTIZATION")
    lat0, lon0 = signed(grid, 46, 4), unsigned(grid, 50, 4)
    lat1, lon1 = signed(grid, 55, 4), unsigned(grid, 59, 4)
    require(lat0 - j_step*(ny-1) == lat1 and (lon0+i_step*(nx-1)) % 360000000 == lon1,
            "GRID_ENDPOINT_MISMATCH")
    lat_scaled, lon_scaled = round(latitude*1000000), round(longitude*1000000)
    row, residual_lat = divmod(lat0 - lat_scaled, j_step)
    col, residual_lon = divmod((lon_scaled - lon0) % 360000000, i_step)
    require(latitude*1000000 == lat_scaled and longitude*1000000 == lon_scaled and
            residual_lat == residual_lon == 0 and 0 <= row < ny and 0 <= col < nx, "QUERY_NOT_ON_REGISTERED_GRID")
    return nx * row + col, nx*ny


def prefix_sections(prefix, total_length):
    require(len(prefix) >= 16 and prefix[:4] == b"GRIB" and prefix[6:8] == b"\x00\x02" and
            unsigned(prefix, 8, 8) == total_length, "INVALID_GRIB_FIELD_BOUNDARY")
    seam, sections = 16, {}
    for expected in (1, 3, 4, 5, 6):
        size, section = unsigned(prefix, seam, 4), unsigned(prefix, seam+4, 1)
        require(section == expected and size >= 5 and seam+size <= len(prefix), "UNSUPPORTED_GRIB_SECTION_LAYOUT")
        sections[section] = prefix[seam:seam+size]
        seam += size
    end_size, end_section = unsigned(prefix, seam, 4), unsigned(prefix, seam+4, 1)
    require(end_section == 7 and seam + end_size == total_length-4, "INCONSISTENT_GRIB_PACKED_FIELD_SIZE")
    return sections, prefix[seam+5:min(len(prefix), total_length-4)], end_size-5


def integer_at(data, packing, packed_length, index, n):
    require(len(packing) == 49 and unsigned(packing, 9, 2) == 3 and packing[21:23] == b"\x01\x00" and
            unsigned(packing, 5, 4) == n, "UNSUPPORTED_FIELD_PACKING_OR_MISSING_VALUES")
    ref_bits, groups = packing[19], unsigned(packing, 31, 4)
    width_ref, width_bits = packing[35], packing[36]
    span_ref, span_inc = unsigned(packing, 37, 4), packing[41]
    tail, span_bits = unsigned(packing, 42, 4), packing[46]
    order, extra = packing[47:49]
    require(order in (1, 2) and 1 <= extra <= 8 and 1 <= groups <= n and span_inc > 0 and
            all(0 <= count <= 32 for count in (ref_bits, width_bits, span_bits)), "UNSUPPORTED_DIFFERENCE_GROUP_METADATA")
    initial = [signed(data, i*extra, extra) for i in range(order)]
    minimum = signed(data, order*extra, extra)
    if index < order:
        return initial[index], (order+1)*extra
    ref_base = (order+1)*extra*8
    width_base = 8*((ref_base + groups*ref_bits + 7)//8)
    span_base = 8*((width_base + groups*width_bits + 7)//8)
    values_base = 8*((span_base + groups*span_bits + 7)//8)
    require(values_base <= len(data)*8, "PREFIX_DOES_NOT_CONTAIN_GROUP_TABLES")
    widths = [width_ref + bits(data, width_base+i*width_bits, width_bits) for i in range(groups)]
    lengths = [span_ref + span_inc*bits(data, span_base+i*span_bits, span_bits) for i in range(groups-1)] + [tail]
    require(sum(lengths) == n and all(0 <= width <= 32 for width in widths) and
            values_base + sum(width*k for width, k in zip(widths, lengths, strict=True)) <= packed_length*8,
            "PACKING_DIMENSIONS_UNSUPPORTED")
    previous, velocity = initial[-1], (initial[-1] - initial[0] if order == 2 else 0)
    cell, pointer = 0, values_base
    for g, (width, length) in enumerate(zip(widths, lengths, strict=True)):
        stop = min(cell+length, index+1)
        first = max(order, cell)
        count = max(0, stop-first)
        if count:
            ref = bits(data, ref_base+g*ref_bits, ref_bits)+minimum
            if width == 0:
                previous += ref*count if order == 1 else count*velocity + ref*count*(count+1)//2
                velocity += ref*count
            else:
                place = pointer + (first-cell)*width
                require(place + count*width <= len(data)*8, "POINT_EXCEEDS_EXPERIMENTAL_PREFIX")
                for i in range(count):
                    delta = ref + bits(data, place + i*width, width)
                    if order == 1:
                        previous += delta
                    else:
                        velocity += delta
                        previous += velocity
        if stop == index+1:
            return previous, (pointer + (stop-cell)*width + 7)//8
        pointer += width*length
        cell += length
    raise ValueError("QUERY_INDEX_OUTSIDE_PACKED_GRID")


def forecast_at(prefix, total_length, spec):
    sections, body, packed_bytes = prefix_sections(prefix, total_length)
    clock, grid, forecast, packing, bitmap = (sections[s] for s in (1, 3, 4, 5, 6))
    require(len(clock) == 21 and unsigned(clock, 5, 2) == 7, "SOURCE_IS_NOT_NCEP_GFS")
    origin = datetime(unsigned(clock, 12, 2), clock[14], clock[15], clock[16], clock[17], clock[18], tzinfo=timezone.utc)
    require(origin.strftime("%Y%m%d%H") == spec["day"]+spec["cycle"] and origin.minute == origin.second == 0,
            "FORECAST_ORIGIN_TIME_MISMATCH")
    require(len(forecast) == 34 and unsigned(forecast, 7, 2) == 0 and forecast[9:11] == b"\0\0" and
            forecast[17] == 1 and unsigned(forecast, 18, 4) == 24 and forecast[22:28] == b"\x67\0\0\0\0\x02" and
            bitmap == b"\0\0\0\x06\x06\xff", "FORECAST_IS_NOT_EXACT_BOUND_TEMPERATURE_FIELD")
    index, count = ordered_grid(grid, spec["latitude"], spec["longitude"])
    unpacked, needed = integer_at(body, packing, packed_bytes, index, count)
    base = struct.unpack(">f", packing[11:15])[0]
    value = (base + unpacked * 2.0**signed(packing, 15, 2)) * 10.0**(-signed(packing, 17, 2))
    require(isfinite(value), "NONFINITE_FORECAST_VALUE")
    return {"temperature_k": value, "index": index, "message_bytes": total_length,
            "packed_bytes_needed_through_point": needed, "reference_time_utc": origin.isoformat()}
