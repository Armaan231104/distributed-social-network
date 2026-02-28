'use strict';

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

window.addEventListener('load', () => {
  const openBtn = document.getElementById('open-create-post');
  const modal = document.getElementById('new-post-modal');
  const closeBtn = document.getElementById('close-create-post');
  const form = document.getElementById('new-post-form');

  const typeSelect = document.getElementById('content-type-select');
  const imageInput = document.getElementById('image-input');

  function openModal() {
    modal.classList.remove('hidden');
  }

  function closeModal() {
    modal.classList.add('hidden');
    form.reset();
    imageInput.style.display = 'none';
  }

  openBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);

  // Click outside modal-content closes it
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  // Show/hide image input depending on contentType
  typeSelect.addEventListener('change', () => {
    if (typeSelect.value === 'image') {
      imageInput.style.display = 'block';
    } else {
      imageInput.style.display = 'none';
      imageInput.value = '';
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const csrf = getCookie('csrftoken');
    const contentType = typeSelect.value;

    try {
      let res;

      if (contentType === 'image') {
        const fd = new FormData(form);

        // enforce image required
        if (!fd.get('image') || fd.get('image').name === '') {
          alert('Please choose an image file.');
          return;
        }

        res = await fetch('/posts/api/entries/create/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrf,
          },
          body: fd
        });
      } else {
        // JSON request for text/plain or text/markdown
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
      // simplest: reload so the new post appears
      window.location.reload();

    } catch (err) {
      console.error(err);
      alert('Network error creating post.');
    }
  });
});