'use strict';

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

window.addEventListener('load', () => {
  // MODAL ELEMENTS
  const openBtn = document.getElementById('open-create-post');
  const modal = document.getElementById('new-post-modal');
  const closeBtn = document.getElementById('close-create-post');
  const form = document.getElementById('new-post-form');
  const typeSelect = document.getElementById('content-type-select');
  const visibilitySelect = document.getElementById('visibility-select');
  const textarea = form.querySelector('textarea[name="content"]');

  // NORMAL IMAGE ELEMENTS
  const imageInput = document.getElementById('image-input');
  const imageBox = document.getElementById('image-upload-box');
  const imageRow = document.getElementById('image-row');
  const clearBtn = document.getElementById('clear-image');

  // MARKDOWN IMAGE ELEMENTS
  const markdownImageInput = document.getElementById('markdown-image-input');
  const markdownImageRow = document.getElementById('markdown-image-row');
  const markdownImageBox = document.getElementById('markdown-image-upload-box');
  const uploadMarkdownImageBtn = document.getElementById('upload-markdown-image-btn');
  const markdownImageStatus = document.getElementById('markdown-image-status');

  // HELPER FUNCTIONS
  function resetImageState() {
    imageInput.value = '';
    imageBox.style.backgroundImage = '';
    imageBox.classList.remove('has-image');
  }

  function resetMarkdownImageState() {
    markdownImageInput.value = '';
    markdownImageBox.style.backgroundImage = '';
    markdownImageBox.classList.remove('has-image');
    markdownImageStatus.textContent = '';
  }

  function openModal() {
    modal.classList.remove('hidden');
  }

  function closeModal() {
    modal.classList.add('hidden');
    form.reset();
    textarea.style.display = 'block';
    imageRow.style.display = 'none';
    markdownImageRow.style.display = 'none';
    resetImageState();
    resetMarkdownImageState();
    typeSelect.value = 'text/plain';
  }

  // EVENT LISTENERS
  openBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', e => { if(e.target === modal) closeModal(); });

  typeSelect.addEventListener('change', () => {
    if(typeSelect.value === 'image'){
      imageRow.style.display = 'flex';
      markdownImageRow.style.display = 'none';
      resetMarkdownImageState();
    } else if(typeSelect.value === 'text/markdown'){
      imageRow.style.display = 'none';
      resetImageState();
      markdownImageRow.style.display = 'flex';
    } else {
      imageRow.style.display = 'none';
      markdownImageRow.style.display = 'none';
      resetImageState();
      resetMarkdownImageState();
    }
  });

  // NORMAL IMAGE HANDLERS
  imageBox.addEventListener('click', () => imageInput.click());
  imageInput.addEventListener('change', () => {
    const file = imageInput.files[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = e => {
      imageBox.style.backgroundImage = `url('${e.target.result}')`;
      imageBox.classList.add('has-image');
    };
    reader.readAsDataURL(file);
  });
  clearBtn.addEventListener('click', e => { e.stopPropagation(); resetImageState(); });

  // MARKDOWN IMAGE HANDLERS
  if(markdownImageBox && uploadMarkdownImageBtn){
    let selectedFile = null;

    markdownImageBox.addEventListener('click', () => markdownImageInput.click());

    markdownImageInput.addEventListener('change', () => {
      const file = markdownImageInput.files[0];
      if(!file) return;
      selectedFile = file;

      const reader = new FileReader();
      reader.onload = e => {
        markdownImageBox.style.backgroundImage = `url('${e.target.result}')`;
        markdownImageBox.classList.add('has-image');
      };
      reader.readAsDataURL(file);

      markdownImageStatus.textContent = '';
    });

    uploadMarkdownImageBtn.addEventListener('click', async () => {
      if(!selectedFile){
        markdownImageStatus.textContent = 'Please select an image first.';
        return;
      }

      const csrf = getCookie('csrftoken');
      markdownImageStatus.textContent = 'Uploading image...';

      const fd = new FormData();
      fd.append('image', selectedFile);

      try{
        const res = await fetch('/posts/api/images/upload/', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf },
          body: fd
        });

        const data = await res.json().catch(() => ({}));

        if(!res.ok){
          markdownImageStatus.textContent = data.error || 'Upload failed. Check file type or size.';
          return;
        }

        textarea.value += `\n![Uploaded image](${data.url})\n`;
        markdownImageStatus.textContent = 'Image uploaded and link inserted.';

        // Reset
        selectedFile = null;
        markdownImageInput.value = '';
        markdownImageBox.style.backgroundImage = '';
        markdownImageBox.classList.remove('has-image');

      }catch(err){
        console.error(err);
        markdownImageStatus.textContent = 'Network error uploading image.';
      }
    });
  }

  // FORM SUBMISSION
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const csrf = getCookie('csrftoken');
    const contentType = typeSelect.value;
    try{
      let res;
      if(contentType === 'image'){
        const fd = new FormData(form);
        if(!fd.get('image') || fd.get('image').name === ''){
          alert('Please choose an image file.');
          return;
        }
        res = await fetch('/posts/api/entries/', { method:'POST', headers:{'X-CSRFToken':csrf}, body:fd });
      } else {
        const payload = {
          title: form.elements.title.value,
          content: form.elements.content.value,
          contentType: contentType,
          visibility: visibilitySelect.value
        };
        res = await fetch('/posts/api/entries/', { method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:JSON.stringify(payload) });
      }
      if(!res.ok){
        const err = await res.json().catch(()=>({}));
        alert(err.error || 'Failed to create post.');
        return;
      }
      closeModal();
      window.location.reload();
    }catch(err){
      console.error(err);
      alert('Network error creating post.');
    }
  });
});