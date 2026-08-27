package com.solarMonitor.android.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.solarMonitor.android.api.ApiClientFactory
import com.solarMonitor.android.api.CurrentResponse
import com.solarMonitor.android.api.DaySummary
import com.solarMonitor.android.api.HealthResponse
import com.solarMonitor.android.data.SettingsRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class MonitorUiState(
    val baseUrl: String = "",
    val apiToken: String = "",
    val loading: Boolean = false,
    val error: String? = null,
    val health: HealthResponse? = null,
    val current: CurrentResponse? = null,
    val daySummary: DaySummary? = null,
    val lastRefreshAt: Long? = null,
)

class MonitorViewModel(
    private val settings: SettingsRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(MonitorUiState())
    val state: StateFlow<MonitorUiState> = _state.asStateFlow()

    private var pollJob: Job? = null

    init {
        viewModelScope.launch {
            combine(settings.baseUrl, settings.apiToken) { url, token -> url to token }
                .collect { (url, token) ->
                    _state.update { it.copy(baseUrl = url, apiToken = token) }
                    restartPolling()
                }
        }
    }

    fun updateBaseUrl(value: String) {
        viewModelScope.launch { settings.setBaseUrl(value) }
    }

    fun updateApiToken(value: String) {
        viewModelScope.launch { settings.setApiToken(value) }
    }

    fun refreshNow() {
        viewModelScope.launch { refreshOnce() }
    }

    private fun restartPolling() {
        pollJob?.cancel()
        pollJob = viewModelScope.launch {
            while (isActive) {
                refreshOnce()
                delay(20_000)
            }
        }
    }

    private suspend fun refreshOnce() {
        val url = _state.value.baseUrl
        val token = _state.value.apiToken
        if (url.isBlank()) {
            _state.update { it.copy(error = "Set API base URL in Settings") }
            return
        }
        _state.update { it.copy(loading = true, error = null) }
        try {
            val api = ApiClientFactory.create(url, token)
            val health = api.health()
            val current = api.current()
            val day = api.daySummary()
            _state.update {
                it.copy(
                    loading = false,
                    error = null,
                    health = health,
                    current = current,
                    daySummary = day,
                    lastRefreshAt = System.currentTimeMillis(),
                )
            }
        } catch (e: Exception) {
            _state.update {
                it.copy(
                    loading = false,
                    error = e.message ?: e.javaClass.simpleName,
                )
            }
        }
    }

    companion object {
        fun factory(settings: SettingsRepository): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return MonitorViewModel(settings) as T
                }
            }
    }
}
