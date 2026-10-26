document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('download-details-btn')
  if (!btn) return

  btn.addEventListener('click', async () => {
    const source = document.getElementById('pdf-content')
    const originalLabel = btn.innerHTML

    btn.disabled = true
    btn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-2"></span>Preparing PDF...'

    // html2canvas offsets the capture by the scroll position, so capture from the top
    const prevScrollX = window.scrollX
    const prevScrollY = window.scrollY
    window.scrollTo(0, 0)

    // Off-screen wrapper with a fixed desktop width, so the layout is the same on every device
    const RENDER_WIDTH = 1400
    const wrapper = document.createElement('div')
    Object.assign(wrapper.style, {
      position: 'absolute',
      top: '0',
      left: '-10000px',
      width: RENDER_WIDTH + 'px',
      padding: '40px',
      background: '#ffffff',
      boxSizing: 'border-box'
    })

    try {
      // Wait for web fonts so the title renders in the right typeface
      await document.fonts.ready

      // Work on a copy so the live page never changes
      const clone = source.cloneNode(true)

      // Force side-by-side row layout regardless of screen size
      clone.querySelectorAll('.row').forEach(row => {
        Object.assign(row.style, {
          display: 'flex',
          flexWrap: 'nowrap',
          alignItems: 'flex-start',
          gap: '24px',
          margin: '0'
        })
      })

      const cols = clone.querySelectorAll('.row > [class*="col-"]')
      cols.forEach((col, i) => {
        Object.assign(col.style, {
          flex: i === 0 ? '2 1 0' : '1 1 0', // 2/3 abstract, 1/3 details
          width: 'auto',
          maxWidth: 'none',
          minWidth: '0',
          padding: '0',
          margin: '0'
        })
      })

      // Remove the download button from the PDF and the gap left above it
      clone.querySelector('#download-details-btn')?.remove()
      clone
        .querySelectorAll('.detail-meta-item.mb-5')
        .forEach(el => el.classList.remove('mb-5'))

      wrapper.appendChild(clone)
      document.body.appendChild(wrapper)

      const canvas = await html2canvas(wrapper, {
        scale: 3, // higher = sharper text
        useCORS: true,
        backgroundColor: '#ffffff',
        scrollX: 0,
        scrollY: 0,
        windowWidth: RENDER_WIDTH
      })

      // Landscape A4, image scaled to fit on a single page
      const { jsPDF } = window.jspdf
      const pdf = new jsPDF({
        unit: 'mm',
        format: 'a4',
        orientation: 'landscape'
      })

      const margin = 10
      const pageW = pdf.internal.pageSize.getWidth()
      const pageH = pdf.internal.pageSize.getHeight()
      const availW = pageW - margin * 2
      const availH = pageH - margin * 2

      const ratio = Math.min(availW / canvas.width, availH / canvas.height)
      const imgW = canvas.width * ratio
      const imgH = canvas.height * ratio
      const x = (pageW - imgW) / 2
      const y = margin

      pdf.addImage(
        canvas.toDataURL('image/jpeg', 1.0),
        'JPEG',
        x,
        y,
        imgW,
        imgH
      )
      pdf.save(btn.dataset.filename)
    } catch (err) {
      console.error('PDF generation failed:', err)
      alert('Could not generate the PDF. Please try again.')
    } finally {
      wrapper.remove()
      window.scrollTo(prevScrollX, prevScrollY)
      btn.disabled = false
      btn.innerHTML = originalLabel
    }
  })
})
