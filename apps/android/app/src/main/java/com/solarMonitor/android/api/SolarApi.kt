package com.solarMonitor.android.api

import retrofit2.http.GET

interface SolarApi {
    @GET("health")
    suspend fun health(): HealthResponse

    @GET("v1/current")
    suspend fun current(): CurrentResponse

    @GET("v1/day-summary")
    suspend fun daySummary(): DaySummary
}
