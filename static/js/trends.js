// TRENDS PAGE (loaded only by trends.html, after Chart.js)
;(() => {
  'use strict'

  const COLORS = {
    thesis: '#363130',
    capstone: '#da602c',
    program: ['#bf480d', '#363130', '#e97746', '#8a8584', '#f8b396']
  }

  function getTrendsData () {
    const el = document.getElementById('trends-data')
    return el ? JSON.parse(el.textContent) : null
  }

  function escapeHtml (str) {
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
  }

  // Shared tooltip look
  const tooltipStyle = {
    backgroundColor: '#262626',
    titleColor: '#ffffff',
    bodyColor: '#f0f0f0',
    titleFont: { family: 'Inter', weight: '600', size: 12 },
    bodyFont: { family: 'Inter', size: 12 },
    padding: 12,
    cornerRadius: 10,
    boxPadding: 4,
    usePointStyle: true
  }

  /* Yearly Research Output: grouped bars */
  function renderYearlyOutputChart (yearly) {
    const ctx = document.getElementById('yearlyOutputChart')
    if (!ctx) return

    const series = [
      { name: 'Thesis', idx: 0, color: COLORS.thesis },
      { name: 'Capstone', idx: 1, color: COLORS.capstone }
    ]

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: yearly.map(y => y.year),
        datasets: series.map(s => ({
          label: s.name,
          data: yearly.map(y => y.data[s.idx]),
          backgroundColor: s.color,
          hoverBackgroundColor: s.color,
          borderRadius: 8,
          borderSkipped: false,
          barPercentage: 0.85,
          categoryPercentage: 0.75
        }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'top',
            align: 'end',
            labels: {
              usePointStyle: true,
              pointStyle: 'circle',
              boxWidth: 8,
              boxHeight: 8,
              padding: 16,
              font: { family: 'Inter', size: 11 },
              color: '#555'
            }
          },
          tooltip: tooltipStyle
        },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: { font: { family: 'Inter', size: 11 }, color: '#777' }
          },
          y: {
            beginAtZero: true,
            grace: '10%',
            border: { display: false },
            ticks: {
              precision: 0,
              padding: 8,
              font: { family: 'Inter', size: 10 },
              color: '#999'
            },
            grid: { color: '#f1f1f1', drawTicks: false }
          }
        }
      }
    })
  }

  /* Research Distribution: doughnut with total in the middle */
  const centerTotal = {
    id: 'centerTotal',
    afterDraw (chart) {
      const { ctx, chartArea } = chart
      if (!chartArea) return
      const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0)
      const x = (chartArea.left + chartArea.right) / 2
      const y = (chartArea.top + chartArea.bottom) / 2

      ctx.save()
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = '#1a1a1a'
      ctx.font = '700 28px MuseoModerno, Inter, sans-serif'
      ctx.fillText(total.toLocaleString(), x, y - 8)
      ctx.fillStyle = '#888'
      ctx.font = '500 11px Inter, sans-serif'
      ctx.fillText('papers', x, y + 16)
      ctx.restore()
    }
  }

  function renderResearchDistributionChart (dist) {
    const ctx = document.getElementById('researchDistributionChart')
    if (!ctx) return

    new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: dist.labels,
        datasets: [
          {
            data: dist.data,
            backgroundColor: dist.labels.map(
              (_, i) => COLORS.program[i % COLORS.program.length]
            ),
            borderColor: '#fdfdfd',
            borderWidth: 3,
            borderRadius: 6,
            hoverOffset: 8
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '66%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              font: { family: 'Inter', size: 11 },
              color: '#555',
              usePointStyle: true,
              pointStyle: 'circle',
              boxWidth: 8,
              boxHeight: 8,
              padding: 14
            }
          },
          tooltip: {
            ...tooltipStyle,
            callbacks: {
              label: item => {
                const total = item.dataset.data.reduce((a, b) => a + b, 0)
                const pct = total ? Math.round((item.parsed / total) * 100) : 0
                return ` ${item.label}: ${item.parsed} papers (${pct}%)`
              }
            }
          }
        }
      },
      plugins: [centerTotal]
    })
  }

  /* Topic Heat Map */
  function getHeatmapSwatchClass (value, max) {
    const r = value / max
    if (r <= 0.2) return 'heatmap-swatch-1'
    if (r <= 0.4) return 'heatmap-swatch-2'
    if (r <= 0.6) return 'heatmap-swatch-3'
    if (r <= 0.8) return 'heatmap-swatch-4'
    return 'heatmap-swatch-5'
  }

  function attachHeatmapTooltip (grid, heatmap) {
    const tip = document.createElement('div')
    tip.className = 'heatmap-tooltip'
    document.body.appendChild(tip)

    const show = e => {
      const seg = e.target.closest('.heatmap-segment')
      if (!seg) {
        tip.style.opacity = '0'
        return
      }

      const topic = heatmap.topics[seg.dataset.t]
      const year = heatmap.years[seg.dataset.i]
      const n = heatmap.data[topic][seg.dataset.i]

      tip.innerHTML =
        `<div class="heatmap-tooltip-title">${escapeHtml(topic)}</div>` +
        `${year}: ${n} paper${n === 1 ? '' : 's'}`

      // keep it inside the viewport
      const x = e.clientX + 14
      const y = e.clientY + 14
      const w = tip.offsetWidth
      tip.style.left =
        (x + w > window.innerWidth ? e.clientX - w - 14 : x) + 'px'
      tip.style.top = y + 'px'
      tip.style.opacity = '1'
    }

    grid.addEventListener('pointermove', show)
    grid.addEventListener('pointerdown', show) // tap on mobile
    grid.addEventListener('pointerleave', () => {
      tip.style.opacity = '0'
    })
  }

  function renderTopicHeatmap (heatmap) {
    const grid = document.getElementById('heatmapGrid')
    if (!grid) return

    const { years, topics, data } = heatmap
    if (!topics.length) {
      grid.innerHTML =
        '<p class="text-muted mb-0">No categorized papers yet.</p>'
      return
    }

    // label column + one column per year
    grid.style.gridTemplateColumns = `clamp(120px, 32vw, 170px) repeat(${years.length}, 1fr)`

    const max = Math.max(1, ...topics.flatMap(t => data[t]))

    // sticky header row: empty corner + one label per year
    let html = '<div class="heatmap-corner"></div>'
    years.forEach(year => {
      html += `<div class="heatmap-year-label">${year}</div>`
    })

    topics.forEach((topic, t) => {
      const safeTopic = escapeHtml(topic)
      html += `<div class="heatmap-row-label">${safeTopic}</div>`

      data[topic].forEach((value, i) => {
        const swatchClass = getHeatmapSwatchClass(value, max)
        const isFirst = i === 0
        const isLast = i === data[topic].length - 1
        const positionClass = isFirst
          ? 'heatmap-segment-first'
          : isLast
          ? 'heatmap-segment-last'
          : ''

        html += `<div class="heatmap-segment ${swatchClass} ${positionClass}" data-t="${t}" data-i="${i}"></div>`
      })
    })

    grid.innerHTML = html
    attachHeatmapTooltip(grid, heatmap)
  }

  document.addEventListener('DOMContentLoaded', function () {
    const trends = getTrendsData()
    if (!trends || typeof Chart === 'undefined') return

    Chart.defaults.font.family = 'Inter, sans-serif'

    renderYearlyOutputChart(trends.yearly)
    renderResearchDistributionChart(trends.distribution)
    renderTopicHeatmap(trends.heatmap)
  })
})()