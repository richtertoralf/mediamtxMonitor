import unittest

from bin.connection_history import (
    average_rate,
    build_history_sample,
    jitter_history,
    rate_history,
    summarize_history,
)


class HistorySampleTests(unittest.TestCase):
    def test_srt_sample_contains_only_available_normalized_values(self):
        sample = build_history_sample(
            {
                "bitrate_mbps": 4.25,
                "transport_rtt_ms": 31,
                "srt_latency_ms": 1500,
                "srt_health": {
                    "link_capacity_mbps": 11.4,
                    "retrans_packets": 2,
                    "drop_packets": 0,
                },
            },
            "reader",
            100.5,
        )

        self.assertEqual(
            sample,
            {
                "timestamp": 100.5,
                "tx_mbps": 4.25,
                "transport_rtt_ms": 31,
                "srt_latency_ms": 1500,
                "link_capacity_mbps": 11.4,
                "retrans_packets": 2,
                "drop_packets": 0,
            },
        )

    def test_non_srt_sample_does_not_invent_timing_or_srt_values(self):
        sample = build_history_sample(
            {"bitrate_mbps": None},
            "publisher",
            200.0,
        )

        self.assertEqual(sample, {"timestamp": 200.0})
        self.assertNotIn("transport_rtt_ms", sample)
        self.assertNotIn("retrans_packets", sample)

    def test_rtmp_discard_delta_is_stored_without_changing_srt_events(self):
        sample = build_history_sample(
            {"bitrate_mbps": 4.5, "frame_discard_delta": 3},
            "reader",
            202.0,
        )
        self.assertEqual(sample, {
            "timestamp": 202.0,
            "tx_mbps": 4.5,
            "frame_discard_delta": 3,
        })

    def test_protocol_gauges_and_counter_deltas_share_the_compact_history(self):
        sample = build_history_sample({
            "protocol_metrics": {
                "gauges": {"jitter_ms": 4.5},
                "counter_deltas": {"loss": 2, "rtp_error": 0},
            },
        }, "publisher", 203.0)
        self.assertEqual(sample, {
            "timestamp": 203.0,
            "jitter_ms": 4.5,
            "protocol_counter_deltas": {"loss": 2, "rtp_error": 0},
        })


class HistorySummaryTests(unittest.TestCase):
    def test_constant_transport_rtt_supports_partial_startup_history(self):
        samples = [
            {"timestamp": timestamp, "transport_rtt_ms": 80}
            for timestamp in (96.0, 98.0, 100.0)
        ]

        summary = summarize_history(samples, 100.0)

        expected = {
            "sample_count": 3,
            "p50_ms": 80.0,
            "p95_ms": 80.0,
            "variation_ms": 0.0,
        }
        self.assertEqual(summary["timing_source"], "transport_rtt_ms")
        self.assertEqual(summary["timing"]["10s"], expected)
        self.assertEqual(summary["timing"]["60s"], expected)
        self.assertEqual(summary["p50_delta_ms"], 0.0)

    def test_windows_use_real_timestamps_and_linear_percentiles(self):
        samples = [
            {"timestamp": timestamp, "transport_rtt_ms": timestamp}
            for timestamp in range(1, 61)
        ]

        summary = summarize_history(samples, 60.0)

        self.assertEqual(
            summary["timing"]["10s"],
            {
                "sample_count": 10,
                "p50_ms": 55.5,
                "p95_ms": 59.55,
                "variation_ms": 4.05,
            },
        )
        self.assertEqual(summary["timing"]["60s"]["sample_count"], 60)
        self.assertEqual(summary["timing"]["60s"]["p50_ms"], 30.5)
        self.assertEqual(summary["timing"]["60s"]["p95_ms"], 57.05)
        self.assertEqual(summary["p50_delta_ms"], 25.0)

    def test_srt_rtt_outlier_changes_p95_and_variation_without_classification(self):
        samples = [
            {"timestamp": timestamp, "transport_rtt_ms": value}
            for timestamp, value in enumerate([10] * 19 + [110], start=81)
        ]

        summary = summarize_history(samples, 100.0)

        self.assertEqual(summary["timing_source"], "transport_rtt_ms")
        self.assertEqual(summary["timing"]["60s"]["p50_ms"], 10.0)
        self.assertEqual(summary["timing"]["60s"]["p95_ms"], 15.0)
        self.assertEqual(summary["timing"]["60s"]["variation_ms"], 5.0)
        self.assertNotIn("status", summary)

    def test_interval_events_are_summed_without_another_delta(self):
        samples = [
            {
                "timestamp": 45.0,
                "retrans_packets": 7,
                "loss_packets": 2,
            },
            {
                "timestamp": 55.0,
                "retrans_packets": 3,
                "drop_packets": 1,
                "belated_packets": 0,
            },
            {
                "timestamp": 60.0,
                "retrans_packets": 4,
                "drop_packets": 2,
                "undecrypt_packets": 1,
            },
        ]

        summary = summarize_history(samples, 60.0)

        self.assertEqual(
            summary["events"]["10s"],
            {
                "retrans_packets": 7.0,
                "drop_packets": 3.0,
                "belated_packets": 0.0,
                "undecrypt_packets": 1.0,
            },
        )
        self.assertEqual(summary["events"]["60s"]["retrans_packets"], 14.0)
        self.assertEqual(summary["events"]["60s"]["loss_packets"], 2.0)

    def test_all_srt_impacts_keep_distinct_10_and_60_second_sums(self):
        samples = [
            {
                "timestamp": 45.0,
                "loss_packets": 10,
                "retrans_packets": 20,
                "drop_packets": 30,
                "belated_packets": 40,
                "undecrypt_packets": 50,
            },
            {
                "timestamp": 55.0,
                "loss_packets": 1,
                "retrans_packets": 2,
                "drop_packets": 3,
                "belated_packets": 4,
                "undecrypt_packets": 5,
            },
        ]

        summary = summarize_history(samples, 60.0)

        self.assertEqual(summary["events"]["10s"], {
            "retrans_packets": 2.0,
            "loss_packets": 1.0,
            "drop_packets": 3.0,
            "belated_packets": 4.0,
            "undecrypt_packets": 5.0,
        })
        self.assertEqual(summary["events"]["60s"], {
            "retrans_packets": 22.0,
            "loss_packets": 11.0,
            "drop_packets": 33.0,
            "belated_packets": 44.0,
            "undecrypt_packets": 55.0,
        })

    def test_missing_timing_and_events_do_not_create_placeholders(self):
        self.assertEqual(
            summarize_history([{"timestamp": 100.0, "rx_mbps": 4.2}], 100.0),
            {},
        )

    def test_time_windows_tolerate_skipped_and_delayed_cycles(self):
        timestamps = [41.0, 42.0, 44.4, 45.4, 48.0, 49.0, 51.5, 54.0, 58.8, 60.0]
        samples = [
            {"timestamp": sample_time, "transport_rtt_ms": 50 + index}
            for index, sample_time in enumerate(timestamps)
        ]

        summary = summarize_history(samples, 60.0)

        self.assertEqual(summary["timing"]["10s"]["sample_count"], 4)
        self.assertEqual(summary["timing"]["60s"]["sample_count"], 10)

    def test_frame_discard_windows_sum_interval_deltas_separately(self):
        samples = [
            {"timestamp": 1.0, "frame_discard_delta": 10},
            {"timestamp": 51.0, "frame_discard_delta": 3},
            {"timestamp": 59.0, "frame_discard_delta": 5},
            {"timestamp": 60.0, "frame_discard_delta": 0},
        ]
        summary = summarize_history(samples, 60.0)
        self.assertEqual(summary["frame_discard"], {"10s": 8, "60s": 18})
        self.assertNotIn("events", summary)

    def test_protocol_windows_and_jitter_statistics_use_real_time(self):
        samples = [
            {
                "timestamp": 45.0,
                "jitter_ms": 1.0,
                "protocol_counter_deltas": {"loss": 5},
            },
            {
                "timestamp": 55.0,
                "jitter_ms": 3.0,
                "protocol_counter_deltas": {"loss": 2, "rtp_error": 1},
            },
            {
                "timestamp": 60.0,
                "jitter_ms": 5.0,
                "protocol_counter_deltas": {"loss": 0},
            },
        ]
        summary = summarize_history(samples, 60.0)
        self.assertEqual(summary["protocol_counters"]["10s"], {
            "loss": 2,
            "rtp_error": 1,
        })
        self.assertEqual(summary["protocol_counters"]["60s"]["loss"], 7)
        self.assertEqual(summary["jitter"]["10s"]["current_ms"], 5.0)
        self.assertEqual(jitter_history(samples)[-1], {
            "timestamp": 60.0, "ms": 5.0,
        })


class RateHistoryTests(unittest.TestCase):
    def test_ten_second_average_uses_available_burst_samples_without_mutation(self):
        samples = [
            {"timestamp": 91.0, "tx_mbps": 0.2},
            {"timestamp": 94.0, "tx_mbps": 4.8},
            {"timestamp": 97.0, "tx_mbps": 0.1},
            {"timestamp": 100.0, "tx_mbps": 4.4},
        ]
        original = [dict(sample) for sample in samples]
        self.assertEqual(
            average_rate(samples, "reader", 100.0, 10),
            {"average_mbps": 2.38, "sample_count": 4},
        )
        self.assertEqual(samples, original)

    def test_average_requires_two_numeric_samples(self):
        self.assertIsNone(average_rate(
            [{"timestamp": 100.0, "tx_mbps": 4.2}],
            "reader",
            100.0,
            10,
        ))

    def test_directional_rates_keep_missing_samples_as_gaps(self):
        samples = [
            {"timestamp": 1.0},
            {"timestamp": 2.0, "rx_mbps": 4.25, "tx_mbps": 9.0},
            {"timestamp": 3.0, "rx_mbps": 0},
        ]
        self.assertEqual(rate_history(samples, "publisher"), [
            {"timestamp": 1.0, "mbps": None},
            {"timestamp": 2.0, "mbps": 4.25},
            {"timestamp": 3.0, "mbps": 0.0},
        ])


if __name__ == "__main__":
    unittest.main()
