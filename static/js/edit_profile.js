'use strict';

window.addEventListener('load', () => {
    const imageInput = document.getElementById('id_profileImage');
    const uploadBox = document.getElementById('imageUploadBox');
    const removeBtn = document.getElementById('removeImageBtn');
    const clearCheckbox = document.querySelector('input[name="profileImage-clear"]');

    // show selected image
    imageInput.addEventListener('change', () => {
        const file = imageInput.files[0];
        if (file) {
            if (clearCheckbox) clearCheckbox.checked = false;
            const reader = new FileReader();
            reader.onload = (e) => {
                uploadBox.style.backgroundImage = `url('${e.target.result}')`;
                uploadBox.classList.add('has-image');
            };
            reader.readAsDataURL(file);
        }
    });

    // remove image
    removeBtn.addEventListener('click', () => {
        imageInput.value = '';
        uploadBox.style.backgroundImage = '';
        uploadBox.classList.remove('has-image');
        if (clearCheckbox) clearCheckbox.checked = true;
    });
});