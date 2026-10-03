"""Deterministic checks for proposed schedule blocks."""
import re

def minutes(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d|24:00', value):
        raise ValueError('Use a valid HH:MM time')
    h, m = map(int, value.split(':'))
    return h * 60 + m

def validate(blocks, existing):
    seen = set()
    intervals = []
    for block in blocks:
        bid = block.get('block_id')
        if bid and bid in seen: raise ValueError('Duplicate calendar block')
        if bid: seen.add(bid)
        start, end = minutes(block.get('start_time')), minutes(block.get('end_time'))
        if start >= end: raise ValueError('End time must be after start time')
        intervals.append((start,end,bid))
    for index,(start,end,bid) in enumerate(intervals):
        if any(start < e and s < end for s,e,_ in intervals[index+1:]):
            raise ValueError('The proposed schedule has overlapping blocks')
        for old in existing:
            if not (old.get('locked') or old.get('status') in ('completed','in_progress') or old.get('source') != 'planner'): continue
            old_id = old.get('block_id') or old.get('SK','').removeprefix('BLOCK#')
            if bid == old_id:
                if (start,end) != (minutes(old['start_time']),minutes(old['end_time'])):
                    raise ValueError('A protected calendar block was moved')
            elif start < minutes(old['end_time']) and minutes(old['start_time']) < end:
                raise ValueError('A proposed task conflicts with a calendar commitment')
