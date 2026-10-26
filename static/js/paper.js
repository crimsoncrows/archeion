document.addEventListener('DOMContentLoaded', function () {
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js'

  const container = document.getElementById('pdf-container')
  const loading = document.getElementById('loading')
  const pageCount = document.getElementById('page-count')

  // Retrieve the URL from the data attribute set in the Django template
  const url = container.dataset.pdfUrl

  pdfjsLib
    .getDocument(url)
    .promise.then(pdf => {
      // Just show the total number of pages
      pageCount.textContent = pdf.numPages

      let firstPageRendered = false

      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        pdf.getPage(pageNum).then(page => {
          const canvas = document.createElement('canvas')
          const ctx = canvas.getContext('2d')

          // Scale dictates render resolution. 2.0 keeps it crisp on zooming/retina.
          const scale = 2.0
          const outputScale = window.devicePixelRatio || 1

          const viewport = page.getViewport({ scale: scale })

          canvas.width = Math.floor(viewport.width * outputScale)
          canvas.height = Math.floor(viewport.height * outputScale)
          canvas.style.width = Math.floor(viewport.width) + 'px'
          canvas.style.height = Math.floor(viewport.height) + 'px'

          const transform =
            outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null

          container.appendChild(canvas)

          const renderContext = {
            canvasContext: ctx,
            viewport: viewport,
            transform: transform
          }

          // Wait for the render process to finish
          page.render(renderContext).promise.then(() => {
            // Hide the loading screen as soon as the first page is fully rendered on screen
            if (!firstPageRendered) {
              loading.style.display = 'none'
              firstPageRendered = true
            }
          })
        })
      }
    })
    .catch(err => {
      loading.innerHTML = '<p>Failed to load document.</p>'
      console.error('Error loading PDF:', err)
    })
})
