import unittest

from bin.forward_transmission import (
    NOT_SENDING,
    SENDING,
    UNKNOWN,
    evaluate_transmission,
)


WINDOW = 15.0


def forward(sent, state="forwarding"):
    return {"id": "a", "state": state, "outboundBytes": sent}


def run(*observations):
    """Evaluate (timestamp, destination) pairs in order; return all states."""
    states = []
    previous = None
    for timestamp, destination in observations:
        previous = evaluate_transmission(previous, destination, timestamp, WINDOW)
        states.append(previous)
    return states


class TransmissionEvidenceTests(unittest.TestCase):
    def test_one_observation_is_no_evidence(self):
        (state,) = run((100.0, forward(5_000)))
        self.assertEqual((state.status, state.reason), (UNKNOWN, "first_sample"))
        self.assertIsNone(state.since)

    def test_growth_from_an_unused_counter_is_an_observed_start(self):
        _, second = run((100.0, forward(0)), (105.0, forward(1_000)))
        self.assertEqual((second.status, second.reason), (SENDING, "bytes_growing"))
        self.assertEqual(second.since, 105.0)
        self.assertTrue(second.since_observed)
        self.assertEqual(second.last_growth_at, 105.0)

    def test_running_transmission_names_only_the_first_observation(self):
        _, second, third = run(
            (100.0, forward(5_000)), (105.0, forward(6_000)), (110.0, forward(7_000)),
        )
        self.assertEqual(second.status, SENDING)
        self.assertEqual(second.since, 100.0)
        self.assertFalse(second.since_observed)
        self.assertEqual((third.since, third.since_observed), (100.0, False))
        self.assertEqual(third.last_growth_at, 110.0)

    def test_stopped_growth_ends_the_period(self):
        states = run(
            (100.0, forward(0)), (105.0, forward(1_000)),
            (110.0, forward(1_000)), (115.0, forward(1_000)),
        )
        ended, still = states[2], states[3]
        self.assertEqual((ended.status, ended.reason), (NOT_SENDING, "no_byte_growth"))
        self.assertIsNone(ended.since)
        self.assertEqual(ended.ended_at, 110.0)
        self.assertEqual(ended.last_growth_at, 105.0)
        self.assertEqual(still.ended_at, 110.0)

    def test_native_idle_and_error_states_mean_not_sending(self):
        for native, reason in (("idle", "state_idle"), ("error", "state_error")):
            with self.subTest(native=native):
                (state,) = run((100.0, forward(5_000, state=native)))
                self.assertEqual((state.status, state.reason), (NOT_SENDING, reason))

    def test_unknown_state_or_missing_counter_stays_unknown(self):
        (state,) = run((100.0, forward(5_000, state="other")))
        self.assertEqual((state.status, state.reason), (UNKNOWN, "state_unknown"))
        _, second = run((100.0, forward(None)), (105.0, forward(None)))
        self.assertEqual((second.status, second.reason), (UNKNOWN, "no_byte_counter"))

    def test_gap_beyond_the_window_is_no_fresh_evidence(self):
        _, _, gap = run(
            (100.0, forward(0)), (105.0, forward(1_000)), (125.0, forward(9_000)),
        )
        self.assertEqual((gap.status, gap.reason), (UNKNOWN, "sample_gap"))
        self.assertIsNone(gap.ended_at)
        self.assertEqual(gap.last_growth_at, 105.0)

    def test_counter_reset_is_unknown_and_restart_from_zero_is_observed(self):
        states = run(
            (100.0, forward(0)), (105.0, forward(5_000)),
            (110.0, forward(0)), (115.0, forward(800)),
        )
        self.assertEqual((states[2].status, states[2].reason), (UNKNOWN, "counter_reset"))
        self.assertEqual(states[3].status, SENDING)
        self.assertEqual((states[3].since, states[3].since_observed), (115.0, True))

    def test_resumed_sending_clears_the_end(self):
        states = run(
            (100.0, forward(0)), (105.0, forward(1_000)),
            (110.0, forward(1_000)), (115.0, forward(2_000)),
        )
        resumed = states[3]
        self.assertEqual(resumed.status, SENDING)
        self.assertIsNone(resumed.ended_at)
        self.assertEqual((resumed.since, resumed.since_observed), (115.0, True))

    def test_end_after_an_unknown_gap_uses_the_first_known_stop(self):
        states = run(
            (100.0, forward(0)), (105.0, forward(1_000)),
            (125.0, forward(2_000)), (130.0, forward(2_000)),
        )
        self.assertEqual(states[3].status, NOT_SENDING)
        self.assertEqual(states[3].ended_at, 130.0)
        self.assertEqual(states[3].last_growth_at, 105.0)

    def test_snapshot_form_is_plain_json_data(self):
        _, second = run((100.0, forward(0)), (105.0, forward(1_000)))
        self.assertEqual(second.as_snapshot(), {
            "status": "sending",
            "reason": "bytes_growing",
            "since": 105.0,
            "since_observed": True,
            "last_growth_at": 105.0,
            "ended_at": None,
        })


if __name__ == "__main__":
    unittest.main()
