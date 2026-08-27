package com.solarMonitor.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.solarMonitor.android.data.SettingsRepository
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SolarMonitorApp() {
    val context = LocalContext.current
    val settings = remember { SettingsRepository(context.applicationContext) }
    val vm: MonitorViewModel = viewModel(factory = MonitorViewModel.factory(settings))
    val state by vm.state.collectAsState()
    var tab by remember { mutableIntStateOf(0) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Solar Monitor") },
                actions = {
                    if (state.loading) {
                        Box(
                            modifier = Modifier
                                .padding(end = 8.dp)
                                .size(24.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            CircularProgressIndicator(strokeWidth = 2.dp)
                        }
                    }
                    IconButton(onClick = vm::refreshNow) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = tab == 0,
                    onClick = { tab = 0 },
                    icon = { Icon(Icons.Default.Home, contentDescription = null) },
                    label = { Text("Live") },
                )
                NavigationBarItem(
                    selected = tab == 1,
                    onClick = { tab = 1 },
                    icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                    label = { Text("Settings") },
                )
            }
        },
    ) { padding ->
        when (tab) {
            0 -> LiveScreen(state = state, padding = padding)
            else -> SettingsScreen(
                state = state,
                padding = padding,
                onSave = { url, token ->
                    vm.updateBaseUrl(url)
                    vm.updateApiToken(token)
                },
            )
        }
    }
}

@Composable
private fun LiveScreen(state: MonitorUiState, padding: PaddingValues) {
    val pv = state.current?.livedata?.get("pv_power_kw")?.value
    val load = state.current?.livedata?.get("site_load_power_kw")?.value
    val net = state.current?.livedata?.get("net_power_kw")?.value
    val configuration = LocalConfiguration.current
    val landscape = configuration.screenWidthDp > configuration.screenHeightDp

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .then(
                if (landscape) Modifier else Modifier.verticalScroll(rememberScrollState()),
            )
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        state.error?.let {
            Text(text = it, color = MaterialTheme.colorScheme.error)
        }

        PowerFlowPanel(
            pv = pv,
            load = load,
            net = net,
            modifier = if (landscape) Modifier.weight(1f, fill = false) else Modifier.fillMaxWidth(),
        )

        if (!landscape) {
            val day = state.daySummary
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = "Today (${day?.local_date ?: "…"})",
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(text = "Generated: ${formatKwh(day?.generated_kwh)}")
                    Text(text = "Grid ${day?.grid_direction ?: "net"}: ${formatKwh(day?.grid_kwh)}")
                    Text(text = "Home use: ${formatKwh(day?.home_load_kwh)}")
                }
            }
        }

        state.lastRefreshAt?.let {
            val stamp = SimpleDateFormat("h:mm:ss a", Locale.getDefault()).format(Date(it))
            Text(
                text = "Updated $stamp · ${state.health?.last_collector_run?.status ?: "—"}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            )
        }
    }
}

@Composable
private fun SettingsScreen(
    state: MonitorUiState,
    padding: PaddingValues,
    onSave: (String, String) -> Unit,
) {
    var url by remember(state.baseUrl) { mutableStateOf(state.baseUrl) }
    var token by remember(state.apiToken) { mutableStateOf(state.apiToken) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "Cloud API base URL (DigitalOcean). Default is https://solar.blackmagicsoftware.net. " +
                "Emulator against home API: http://10.0.2.2:8000",
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            label = { Text("API base URL") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        OutlinedTextField(
            value = token,
            onValueChange = { token = it },
            label = { Text("Bearer token (API_AUTH_TOKEN)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
        )
        Button(
            onClick = { onSave(url, token) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Save")
        }
    }
}

private fun formatKwh(n: Double?): String {
    if (n == null) return "—"
    return String.format(Locale.US, "%.2f kWh", n)
}
