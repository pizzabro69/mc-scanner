async function loadServerCharts(serverId) {
    const resp = await fetch(`/api/servers/${serverId}/history?hours=168`);
    const json = await resp.json();
    const data = json.data;

    if (!data || data.length === 0) return;

    const labels = data.map(d => {
        const dt = new Date(d.time * 1000);
        return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) +
            ' ' + dt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    });

    const chartOptions = {
        responsive: true,
        interaction: { intersect: false, mode: 'index' },
        scales: {
            y: { beginAtZero: true, ticks: { color: '#999' }, grid: { color: '#333' } },
            x: {
                ticks: { color: '#999', maxTicksLimit: 12, maxRotation: 45 },
                grid: { color: '#333' },
            },
        },
        plugins: {
            legend: { labels: { color: '#ccc' } },
        },
        pointRadius: 0,
        pointHitRadius: 10,
    };

    // Latency chart
    new Chart(document.getElementById('latencyChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Latency (ms)',
                data: data.map(d => d.latency),
                borderColor: '#4f8cff',
                backgroundColor: 'rgba(79, 140, 255, 0.1)',
                fill: true,
                tension: 0.3,
            }]
        },
        options: chartOptions,
    });

    // Players chart
    new Chart(document.getElementById('playersChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Players Online',
                data: data.map(d => d.players),
                borderColor: '#4caf50',
                backgroundColor: 'rgba(76, 175, 80, 0.1)',
                fill: true,
                tension: 0.3,
            }]
        },
        options: chartOptions,
    });
}
