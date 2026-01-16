"""Test scenarios for QueueManager FIFO ordering.

Tests that MRs are processed in first-in-first-out order,
including ordering by queued_at, get_next behavior, active queue
ordering, and position calculations.
"""
