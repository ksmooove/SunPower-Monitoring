package com.solarMonitor.android.api

data class HealthResponse(
    val status: String? = null,
    val database_ok: Boolean? = null,
    val latest_measurement_at: String? = null,
    val inverter_devices: Int? = null,
    val last_collector_run: CollectorRun? = null,
)

data class CollectorRun(
    val status: String? = null,
    val source: String? = null,
    val finished_at: String? = null,
)

data class CurrentResponse(
    val site_id: String? = null,
    val livedata: Map<String, MetricPoint> = emptyMap(),
    val inverter_power_kw_sum: Double? = null,
)

data class MetricPoint(
    val value: Double? = null,
    val unit: String? = null,
    val time: String? = null,
    val collected_at: String? = null,
    val quality: String? = null,
    val source: String? = null,
)

data class DaySummary(
    val timezone: String? = null,
    val local_date: String? = null,
    val generated_kwh: Double? = null,
    val generated_insufficient_samples: Boolean? = null,
    val grid_kwh: Double? = null,
    val grid_direction: String? = null,
    val grid_insufficient_samples: Boolean? = null,
    val home_load_kwh: Double? = null,
    val home_load_insufficient_samples: Boolean? = null,
)
