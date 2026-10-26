// Downloads the similarity result page as a high-resolution PDF.
// Only .sim-results-main is captured, so the navbar, toasts and feedback
// form (all outside it) never appear. Anything inside it marked with
// data-html2canvas-ignore is skipped too.
//
// html2canvas cannot draw <progress> bars or SVG styled from CSS, and it
// cannot push a table row to the next page. So the report is first copied
// into an off-screen sheet at the exact PDF width, those parts are rebuilt
// with plain inline styles, and spacers are added so nothing is cut in half.
//
// The sheet always gets the desktop layout (PDF_LAYOUT below), whatever the
// device. Without it, phone and tablet media queries would stack the cards
// and bars inside the PDF, so the output changed from device to device.
document.addEventListener('DOMContentLoaded', function () {
  const button = document.getElementById('downloadReport')
  const report = document.querySelector('.sim-results-main')
  if (!button || !report || typeof html2pdf === 'undefined') return

  // Legal (8.5 x 14 in) in mm, and the PDF margins: top, right, bottom, left
  const PAGE_W = 215.9,
    PAGE_H = 355.6
  const MARGIN = [10, 10, 12, 10]
  const INNER_W = PAGE_W - MARGIN[1] - MARGIN[3]
  const INNER_H = PAGE_H - MARGIN[0] - MARGIN[2]
  const SHEET_W = Math.floor((INNER_W * 96) / 25.4) // same px width html2pdf uses
  const PAGE_PX = (SHEET_W * INNER_H) / INNER_W // height of one PDF page in px

  // Fixed desktop layout for the PDF sheet. Scoped to .pdf-sheet so the
  // live page is not affected, and !important so the responsive rules in
  // style.css (max-width 768px / 576px) cannot change it.
  const PDF_LAYOUT = `
    .pdf-sheet .sim-results-main { max-width: none !important; }

    /* Summary row: score card and scale side by side */
    .pdf-sheet .sim-summary { grid-template-columns: 1.15fr 1fr !important; }
    .pdf-sheet .sim-score {
      flex-direction: row !important;
      align-items: center !important;
      text-align: left !important;
    }

    /* Matching sources: text left, bar and percent right, on one line */
    .pdf-sheet .sim-source {
      flex-direction: row !important;
      align-items: center !important;
      gap: 24px !important;
    }
    .pdf-sheet .sim-source-body { flex: 1 1 auto !important; min-width: 0 !important; }
    .pdf-sheet .sim-source-title { word-break: break-word !important; }
    .pdf-sheet .sim-source-score {
      display: flex !important;
      align-items: center !important;
      flex: 0 0 220px !important;
      gap: 12px !important;
    }
    .pdf-sheet .sim-source-pct { flex: 0 0 auto !important; }
  `

  // Blocks that must never be split across two pages, in document order.
  // Outer cards come first, so a card that fits on one page moves as a whole.
  const KEEP_TOGETHER = [
    '.sim-results-main > .text-center',
    '.sim-summary',
    '.alert',
    '.sim-panel',
    '.detail-main-card',
    '.sim-panel-title',
    '.sim-sources-sub',
    '.sim-source',
    '.ffm-table tr',
    '.ffm-legend li',
    '.p-detail-section-label',
    '.p-detail-abstract'
  ].join(', ')

  function bandColor (band) {
    const dot = document.querySelector('.sim-dot-' + band)
    const color = dot && getComputedStyle(dot).backgroundColor
    return color && color !== 'rgba(0, 0, 0, 0)' ? color : '#6c757d'
  }

  // <progress> -> two plain divs with the band color.
  // The width is NOT copied from the screen (that changed per device);
  // the bar stretches to fill the space the PDF layout gives it.
  function rebuildBars (original, copy) {
    const src = original.querySelectorAll('progress')
    copy.querySelectorAll('progress').forEach(function (bar, i) {
      const cs = getComputedStyle(src[i])
      const band = (
        Array.from(bar.classList).find(c => c.startsWith('sim-bar-')) || ''
      ).replace('sim-bar-', '')
      const pct = Math.max(
        0,
        Math.min(100, (Number(bar.value) / Number(bar.max || 100)) * 100)
      )
      const track =
        cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)'
          ? cs.backgroundColor
          : '#e9ecef'
      const radius = cs.borderRadius !== '0px' ? cs.borderRadius : '999px'
      const height = parseFloat(cs.height) > 0 ? cs.height : '12px'

      const outer = document.createElement('div')
      Object.assign(outer.style, {
        display: 'block',
        flex: '1 1 auto',
        minWidth: '0',
        height: height,
        background: track,
        borderRadius: radius,
        overflow: 'hidden',
        border: '0'
      })
      const fill = document.createElement('div')
      Object.assign(fill.style, {
        width: pct + '%',
        height: '100%',
        background: bandColor(band),
        borderRadius: radius
      })
      outer.appendChild(fill)
      bar.replaceWith(outer)
    })
  }

  // Adds invisible break points (zero-width spaces) after _ - . / and every
  // 20 characters, so long filenames wrap. html2canvas ignores CSS like
  // word-break: break-all and draws such text in the wrong place, but it
  // does respect these characters, so the browser and the PDF wrap alike.
  function breakable (text) {
    return text
      .replace(/([_\-./\\])/g, '$1\u200B')
      .replace(/([^\s\u200B]{20})(?=[^\s\u200B])/g, '$1\u200B')
  }

  // Meta list (Sources Found / Checked on / File Analyzed) -> plain table.
  // html2canvas misplaces text inside the CSS grid <dl>, which pushed the
  // values below their labels; tables are drawn reliably.
  function rebuildMeta (copy) {
    copy.querySelectorAll('.sim-meta').forEach(function (dl) {
      const table = document.createElement('table')
      Object.assign(table.style, {
        borderCollapse: 'collapse',
        fontSize: '0.72rem',
        lineHeight: '1.5',
        width: '100%',
        tableLayout: 'fixed'
      })

      // Label column sized to the longest label, value column gets the rest
      const colLabel = document.createElement('col')
      colLabel.style.width = '96px'
      const colValue = document.createElement('col')
      table.append(colLabel, colValue)

      dl.querySelectorAll('dt').forEach(function (dt) {
        const dd = dt.nextElementSibling
        const tr = document.createElement('tr')

        const label = document.createElement('td')
        label.textContent = dt.textContent.trim()
        Object.assign(label.style, {
          color: '#1a1a1a',
          fontWeight: '700',
          padding: '1px 12px 1px 0',
          verticalAlign: 'top'
        })

        const value = document.createElement('td')
        value.textContent = dd && dd.tagName === 'DD' ? breakable(dd.textContent.trim()) : ''
        Object.assign(value.style, {
          color: '#555555',
          padding: '1px 0',
          verticalAlign: 'top'
        })

        tr.append(label, value)
        table.appendChild(tr)
      })

      dl.replaceWith(table)
    })
  }

  // SVG (score ring) -> same SVG with its CSS colors written as attributes
  function inlineSvgStyles (original, copy) {
    const src = original.querySelectorAll('svg')
    copy.querySelectorAll('svg').forEach(function (svg, i) {
      const rect = src[i].getBoundingClientRect()
      const svgStyle = getComputedStyle(src[i])
      svg.setAttribute('width', rect.width)
      svg.setAttribute('height', rect.height)
      if (svgStyle.transform && svgStyle.transform !== 'none')
        svg.style.transform = svgStyle.transform

      const srcShapes = src[i].querySelectorAll('circle, path, rect, line')
      svg
        .querySelectorAll('circle, path, rect, line')
        .forEach(function (shape, j) {
          const cs = getComputedStyle(srcShapes[j])
          ;[
            'stroke',
            'stroke-width',
            'fill',
            'stroke-dasharray',
            'stroke-dashoffset',
            'stroke-linecap',
            'opacity'
          ].forEach(function (prop) {
            const value = cs.getPropertyValue(prop)
            if (value) shape.setAttribute(prop, value)
          })
        })
    })
  }

  // Push any block that would cross a page edge down to the next page
  function paginate (sheet) {
    const top0 = () => sheet.getBoundingClientRect().top
    sheet.querySelectorAll(KEEP_TOGETHER).forEach(function (el) {
      const rect = el.getBoundingClientRect()
      const top = rect.top - top0()
      const bottom = top + rect.height
      if (rect.height === 0 || rect.height > PAGE_PX) return // empty, or too tall to keep whole
      if (Math.floor(top / PAGE_PX) === Math.floor((bottom - 1) / PAGE_PX))
        return // fits already

      const gap = PAGE_PX - (top % PAGE_PX)
      if (el.tagName === 'TR') {
        // a div is not allowed between table rows, so use an empty row
        const spacer = document.createElement('tr')
        const cell = document.createElement('td')
        cell.colSpan = el.children.length || 1
        Object.assign(cell.style, {
          height: gap + 'px',
          padding: '0',
          border: '0',
          background: 'transparent'
        })
        spacer.appendChild(cell)
        el.before(spacer)
      } else {
        const spacer = document.createElement('div')
        spacer.style.height = gap + 'px'
        el.before(spacer)
      }
    })
  }

  button.addEventListener('click', async function () {
    const label = button.textContent
    button.disabled = true
    button.textContent = 'Preparing PDF...'

    // Fixed PDF layout rules, removed again when the export finishes
    const layout = document.createElement('style')
    layout.textContent = PDF_LAYOUT
    document.head.appendChild(layout)

    // Off-screen host; the sheet inside it is what gets printed
    const host = document.createElement('div')
    Object.assign(host.style, {
      position: 'fixed',
      left: '-10000px',
      top: '0',
      zIndex: '-1'
    })
    const sheet = document.createElement('div')
    sheet.className = 'pdf-sheet'
    Object.assign(sheet.style, { width: SHEET_W + 'px', background: '#ffffff' })

    const copy = report.cloneNode(true)
    copy
      .querySelectorAll('[data-html2canvas-ignore]')
      .forEach(el => el.remove())
    sheet.appendChild(copy)
    host.appendChild(sheet)
    document.body.appendChild(host)

    try {
      rebuildBars(report, copy)
      rebuildMeta(copy)
      inlineSvgStyles(report, copy)
      if (document.fonts && document.fonts.ready) await document.fonts.ready
      paginate(sheet)

      const today = new Date().toISOString().slice(0, 10)
      await html2pdf()
        .set({
          margin: MARGIN,
          filename: `archeion-similarity-report-${today}.pdf`,
          image: { type: 'jpeg', quality: 0.98 },
          html2canvas: {
            scale: 3, // HD: 3x the screen resolution
            useCORS: true,
            backgroundColor: '#ffffff',
            scrollX: 0,
            scrollY: 0
          },
          jsPDF: {
            unit: 'mm',
            format: 'legal',
            orientation: 'portrait',
            compress: true
          },
          pagebreak: { mode: ['legacy'] } // page breaks are already handled above
        })
        .from(sheet)
        .save()
    } catch (err) {
      console.error('PDF export failed:', err)
      alert('The report could not be downloaded. Please try again.')
    } finally {
      host.remove()
      layout.remove()
      button.disabled = false
      button.textContent = label
    }
  })
})