//LIVE SIGNUP VALIDATION
// Asks Django (users:validate_signup) to run the real SignUpForm while the
// user types, so full name / username taken / password rules show up
// before submitting instead of turning red only after the page reloads.
const signupForm = document.getElementById('signupForm')

if (signupForm) {
  const liveFields = {
    full_name: document.getElementById('fullName'),
    username: document.getElementById('username'),
    email: document.getElementById('email'),
    password: document.getElementById('password')
  }

  const touched = new Set() // only show results for fields the user has typed in
  let debounceTimer = null
  let pendingRequest = null

  function runLiveValidation () {
    clearTimeout(debounceTimer)
    if (pendingRequest) pendingRequest.abort() // drop outdated responses
    pendingRequest = new AbortController()

    fetch(signupForm.dataset.validateUrl, {
      method: 'POST',
      body: new FormData(signupForm), // includes csrfmiddlewaretoken
      signal: pendingRequest.signal
    })
      .then(res => (res.ok ? res.json() : null)) // 429 = rate limited, just skip
      .then(data => {
        if (!data) return
        touched.forEach(name => {
          setFieldState(liveFields[name], data.errors[name] || '')
        })
      })
      .catch(err => {
        if (err.name !== 'AbortError')
          console.warn('Live validation failed:', err)
      })
  }

  Object.entries(liveFields).forEach(([name, input]) => {
    if (!input) return

    // Check 400ms after the user stops typing
    input.addEventListener('input', () => {
      touched.add(name)
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(runLiveValidation, 400)
    })

    // Check right away when leaving a field
    input.addEventListener('blur', () => {
      if (!input.value.trim()) return
      touched.add(name)
      runLiveValidation()
    })
  })
}
