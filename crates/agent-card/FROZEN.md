# Wire Format Freeze Notice

**Version**: v1.0.0
**Date**: TBD (post 72h validation)
**Status**: DRAFT

The PACR envelope wire format (Primary Header + Extension Headers + Body)
as defined in this repository is hereby frozen.

## Guarantee

- No backward-incompatible changes will ever be made to v1.x
- New Extension Header types may be added (TYPE codes 0x0100–0xFFFE)
- Primary Header structure (104 bytes fixed) will NEVER change
- MAGIC (0x50414352), VERSION_MAJOR (1) interpretation will NEVER change

## Verification

Any v1.0 envelope serialized today MUST be deserializable by any future v1.x parser.

## Rationale

The first real PACR records are now being generated (72h validation: 2,600,000+ records).
Changing wire format after this point would invalidate causal history — a thermodynamic
impossibility (you cannot un-erase erased bits).
