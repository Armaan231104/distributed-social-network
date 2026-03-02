'use strict';

// =====================
// CSRF HELPER
// =====================
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// =====================
// DOM READY
// =====================
window.addEventListener('load', () => {
  // MODAL ELEMENTS
  const openBtn = document.getElementById('open-create-post');
  const modal = document.getElementById('new-post-modal');
  const closeBtn = document.getElementById('close-create-post');
  const form = document.getElementById('new-post-form');

  // INPUTS / BOXES
  const typeSelect = document.getElementById('content-type-select');
  const textarea = form.querySelector('textarea[name="content"]');
  const imageInput = document.getElementById('image-input');
  const imageBox = document.getElementById('image-upload-box');
  const imageRow = document.getElementById('image-row');
  const clearBtn = document.getElementById('clear-image');

  // =====================
  // HELPER FUNCTIONS
  // =====================
  function resetImageState() {
    imageInput.value = '';
    imageBox.style.backgroundImage = '';
    imageBox.classList.remove('has-image');
  }

  function openModal() {
    modal.classList.remove('hidden');
  }

  function closeModal() {
    modal.classList.add('hidden');
    form.reset();
    textarea.style.display = 'block';
    imageRow.style.display = 'none';
    resetImageState();
    typeSelect.value = 'text/plain';
  }

  // =====================
  // EVENT LISTENERS
  // =====================

  // Open / Close modal
  openBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);

  // Click outside modal closes it
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  // Toggle content type
  typeSelect.addEventListener('change', () => {
    if (typeSelect.value === 'image') {
      // textarea.style.display = 'none';
      imageRow.style.display = 'flex';
    } else {
      // textarea.style.display = 'block';
      imageRow.style.display = 'none';
      resetImageState();
    }
  });

  // Image box click triggers file input
  imageBox.addEventListener('click', () => {
    imageInput.click();
  });

  // Image selection
  imageInput.addEventListener('change', () => {
    const file = imageInput.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      imageBox.style.backgroundImage = `url('${e.target.result}')`;
      imageBox.classList.add('has-image'); // hide placeholder content
    };
    reader.readAsDataURL(file);
  });

  // Clear image button
  clearBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetImageState();
  });

  // =====================
  // FORM SUBMISSION
  // =====================
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const csrf = getCookie('csrftoken');
    const contentType = typeSelect.value;

    try {
      let res;

      if (contentType === 'image') {
        const fd = new FormData(form);

        if (!fd.get('image') || fd.get('image').name === '') {
          alert('Please choose an image file.');
          return;
        }

        res = await fetch('/posts/api/entries/create/', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf },
          body: fd
        });

      } else {
        const payload = {
          title: form.elements.title.value,
          content: form.elements.content.value,
          contentType: contentType
        };

        res = await fetch('/posts/api/entries/create/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf
          },
          body: JSON.stringify(payload)
        });
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.error || 'Failed to create post.');
        return;
      }

      closeModal();
      window.location.reload();

    } catch (err) {
      console.error(err);
      alert('Network error creating post.');
    }
  });
});