(() => {
    'use strict'
    const forms = document.querySelectorAll('.needs-validation')
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault()
                event.stopPropagation()
            }
            form.classList.add('was-validated')
        }, false)
    })
})()

document.addEventListener("DOMContentLoaded", function() {
    const toggleBtn = document.getElementById("sidebarToggle");
    const sidebar = document.querySelector(".admin-sidebar");
    const overlay = document.getElementById("sidebarOverlay");

    if (toggleBtn && sidebar && overlay) {
        // Toggle the menu open and closed
        toggleBtn.addEventListener("click", function() {
            sidebar.classList.toggle("show");
            overlay.classList.toggle("show");
        });

        // Close the menu if the user clicks the dark background overlay
        overlay.addEventListener("click", function() {
            sidebar.classList.remove("show");
            overlay.classList.remove("show");
        });
    }
});

document.addEventListener("DOMContentLoaded", function () {
    const tables = document.querySelectorAll(".admin-table");

    tables.forEach(table => {
        const headers = table.querySelectorAll("th");
        
        // 1. Lock in the initial widths of all columns on page load
        // This prevents the browser from auto-adjusting them when you start dragging
        headers.forEach(th => {
            const styles = window.getComputedStyle(th);
            th.style.width = styles.width;
            th.style.minWidth = styles.width;
        });

        headers.forEach(header => {
            // Create the resize handle
            const resizer = document.createElement("div");
            resizer.classList.add("resizer");
            header.appendChild(resizer);
            
            let startX = 0;
            let startColWidth = 0;
            let startTableWidth = 0;

            const mouseDownHandler = function (e) {
                startX = e.clientX;
                
                // Get the starting widths of both the column AND the table
                startColWidth = parseFloat(window.getComputedStyle(header).width);
                startTableWidth = parseFloat(window.getComputedStyle(table).width);

                document.addEventListener("mousemove", mouseMoveHandler);
                document.addEventListener("mouseup", mouseUpHandler);
                
                resizer.classList.add("resizing");
                document.body.style.userSelect = 'none'; // Prevent text highlighting while dragging
            };

            const mouseMoveHandler = function (e) {
                const dx = e.clientX - startX;
                
                // 2. Expand the specific column
                const newColWidth = `${startColWidth + dx}px`;
                header.style.width = newColWidth;
                header.style.minWidth = newColWidth;

                // 3. Expand the ENTIRE table by the same amount 
                // This stops it from crushing the other columns!
                const newTableWidth = `${startTableWidth + dx}px`;
                table.style.width = newTableWidth;
                table.style.minWidth = newTableWidth;
            };

            const mouseUpHandler = function () {
                resizer.classList.remove("resizing");
                document.removeEventListener("mousemove", mouseMoveHandler);
                document.removeEventListener("mouseup", mouseUpHandler);
                document.body.style.userSelect = ''; 
            };

            resizer.addEventListener("mousedown", mouseDownHandler);
        });
    });
});

//WORD COUNTER FOR TEXT INPUT
function countWords() {
    var text = document.getElementById('userInputText').value.trim();
    var count = text === '' ? 0 : text.split(/\s+/).length;
    var counter = document.getElementById('wordCounter');

    if (count >= 2001) {
        counter.textContent = 'Maximum words reached.';
        counter.classList.remove('alert-secondary');
        counter.classList.add('alert-danger');
    } else {
        counter.textContent = count + ' / 2000 words';
        counter.classList.remove('alert-danger');
        counter.classList.add('alert-secondary');
    }
}




//UPDATE ALERT ERRORS
const errors = new Set();

function updateError() {
    const error = document.getElementById('infoError');
    const errorMsg = document.getElementById('infoErrorMsg');
    if (!error || !errorMsg) return; // page has no alert box (e.g. login)

    if (errors.size > 0) {
        error.classList.remove('d-none');
        errorMsg.innerHTML = '<strong>Error/s:</strong> ' + [...errors].join(' ');
    } else {
        error.classList.add('d-none');
        errorMsg.innerHTML = '';
    }
}


//FIELD STATE (shows the message under the input, Bootstrap style)
// Needs a feedback element with id="<inputId>Feedback" and data-default="..."
function setFieldState(input, message) {
    const feedback = document.getElementById(input.id + 'Feedback');

    // Empty field: let the browser's "required" check handle it on submit
    if (!input.value.trim()) {
        input.setCustomValidity('');
        input.classList.remove('is-valid', 'is-invalid');
        if (feedback) feedback.textContent = feedback.dataset.default || '';
        return;
    }

    input.setCustomValidity(message || '');
    input.classList.toggle('is-invalid', !!message);
    input.classList.toggle('is-valid', !message);
    if (feedback) feedback.textContent = message || feedback.dataset.default || '';
}



//VALIDATIONS
function checkPasswordMatch() {
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword');
    const mismatch = confirmPassword.value && password !== confirmPassword.value;

    // Signup page: show the mismatch right under Confirm Password
    if (document.getElementById('confirmPasswordFeedback')) {
        setFieldState(confirmPassword, mismatch ? 'Passwords do not match.' : '');
        return;
    }

    // Other pages: use the alert box at the top
    if (mismatch) {
        errors.add('Passwords do not match.');
        confirmPassword.setCustomValidity('mismatch');
    } else {
        errors.delete('Passwords do not match.');
        confirmPassword.setCustomValidity('');
    }
    updateError();
}

function usernameValidation() {
    const value = document.getElementById('username').value;
    const usernameRegex = /^[a-zA-Z0-9_]+$/;

    if (value === '' || usernameRegex.test(value)) {
        errors.delete('Invalid username.');
    } else {
        errors.add('Invalid username.');
    }
    updateError();
}


//TOGGLES
function togglePass(inputId, span) {
    const input = document.getElementById(inputId);
    const icon = span.querySelector('i');
    if (!input || !icon) return;

    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.replace('bi-eye', 'bi-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.replace('bi-eye-slash', 'bi-eye');
    }
}

// Password eye toggle: any element with data-toggle-pass="<input id>"
document.addEventListener('click', function (e) {
    const toggle = e.target.closest('[data-toggle-pass]');
    if (!toggle) return;
    togglePass(toggle.dataset.togglePass, toggle);
});



//CALLS

if (document.getElementById('confirmPassword')) {
    document.getElementById('confirmPassword').addEventListener('input', checkPasswordMatch);
    // Re-check the match when the main password changes too
    if (document.getElementById('password')) {
        document.getElementById('password').addEventListener('input', checkPasswordMatch);
    }
}

// Signup uses the live Django check instead of this simple regex check
if (document.getElementById('username') && !document.getElementById('signupForm')) {
    document.getElementById('username').addEventListener('input', usernameValidation);
    document.getElementById('username').addEventListener('blur', usernameValidation);
}
if (document.getElementById('userInputText')) {
  document.getElementById('userInputText').addEventListener('input', countWords);
}



//animation
document.addEventListener("DOMContentLoaded", function () {
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  const heroEls = document.querySelectorAll(".js-reveal-hero");

  heroEls.forEach((el, i) => {
    if (prefersReducedMotion) return;

    el.style.opacity = "0";
    el.animate(
      [
        { opacity: 0, transform: "translateY(24px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      {
        duration: 700,
        delay: i * 150,
        easing: "ease",
        fill: "forwards",
      }
    );
  });

  const scrollEls = document.querySelectorAll(".js-reveal-scroll");

  scrollEls.forEach((el) => {
    if (!prefersReducedMotion) {
      el.style.opacity = "0";
    }
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          const el = entry.target;

          if (!prefersReducedMotion) {
            el.animate(
              [
                { opacity: 0, transform: "translateY(32px)" },
                { opacity: 1, transform: "translateY(0)" },
              ],
              {
                duration: 600,
                delay: i * 120,
                easing: "ease",
                fill: "forwards",
              }
            );
          } else {
            el.style.opacity = "1";
          }

          observer.unobserve(el);
        }
      });
    },
    { threshold: 0.15 }
  );

  scrollEls.forEach((el) => observer.observe(el));

  const hoverEls = document.querySelectorAll(
    ".features-card, .landing-card-steps"
  );

  hoverEls.forEach((el) => {
    el.addEventListener("mouseenter", () => {
      el.animate(
        [
          { transform: "translateY(0)", boxShadow: "0 0 0 rgba(0,0,0,0)" },
          {
            transform: "translateY(-6px)",
            boxShadow: "0 12px 24px rgba(0,0,0,0.08)",
          },
        ],
        { duration: 300, easing: "ease", fill: "forwards" }
      );
    });

    el.addEventListener("mouseleave", () => {
      el.animate(
        [
          {
            transform: "translateY(-6px)",
            boxShadow: "0 12px 24px rgba(0,0,0,0.08)",
          },
          { transform: "translateY(0)", boxShadow: "0 0 0 rgba(0,0,0,0)" },
        ],
        { duration: 300, easing: "ease", fill: "forwards" }
      );
    });
  });
});