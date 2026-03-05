// interactions.js

// Like / Unlike a post/entry
function toggleLike(objectType, objectId) {
    fetch(`/interactions/like/${objectType}/${objectId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1],
            'Content-Type': 'application/json',
        },
    })
    .then(res => res.json())
    .then(data => {
        const btn = document.getElementById(`like-btn-${objectId}`);
        btn.innerHTML = `
            <i class="${data.liked ? 'fa-solid fa-heart' : 'fa-regular fa-heart'}"></i>
            <span id="like-count-${objectId}">${data.like_count}</span>
        `;

        const heartIcon = btn.querySelector('i');
        heartIcon.classList.add('pop-heart');

        heartIcon.addEventListener('animationend', () => {
            heartIcon.classList.remove('pop-heart');
        }, { once: true });
    })
    .catch(err => {
        console.error('Like toggle failed:', err);
    });
}

// Toggle post options menu (three dots)
function togglePostOptions(postId) {
    const menu = document.getElementById(`post-options-menu-${postId}`);
    if (!menu) return;

    const willBeVisible = menu.classList.toggle('hidden');

    // If opening this menu, close all others
    if (!willBeVisible) {
        document.querySelectorAll('.post-options-menu:not(.hidden)').forEach(other => {
            if (other !== menu) {
                other.classList.add('hidden');
            }
        });
    }
}

// Close all options menus when clicking outside
document.addEventListener('click', (event) => {
    if (!event.target.closest('.post-options')) {
        document.querySelectorAll('.post-options-menu').forEach(menu => {
            menu.classList.add('hidden');
        });
    }
});

// Prevent outside click from closing when clicking inside the menu
document.addEventListener('click', (event) => {
    if (event.target.closest('.post-options-menu')) {
        event.stopPropagation();
    }
});

const editModal = document.getElementById('edit-description-modal');
const editForm = document.getElementById('edit-description-form');
const editTextarea = document.getElementById('edit-description');
const closeEditBtn = document.getElementById('close-edit-description');
window.openEditPostDescription = function(postId, currentContent) {
    editForm.elements['post_id'].value = postId;
    editTextarea.value = currentContent || '';
    editModal.classList.remove('hidden');
};
// CLOSE
closeEditBtn?.addEventListener('click', () => {
    editModal.classList.add('hidden');
    editForm.reset();
});

editModal?.addEventListener('click', (e) => {
    if (e.target === editModal) {
        editModal.classList.add('hidden');
        editForm.reset();
    }
});

// SUBMIT (only defined once)
editForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const postId = editForm.elements['post_id'].value;
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    if (!csrf) {
        alert("CSRF token missing – refresh page.");
        return;
    }

    try {
        const res = await fetch(`/posts/api/entries/${postId}/update/`, {
            method: 'PUT',
            credentials: 'same-origin',   // 🔥 ADD THIS
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify({
                content: editTextarea.value.trim()
            })
        });

        if (!res.ok) {
            alert("Failed to update post.");
            return;
        }

        editModal.classList.add('hidden');
        window.location.reload(); // simpler & safer
    } catch (err) {
        console.error(err);
        alert("Network error.");
    }
});