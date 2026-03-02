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
        const countSpan = btn.querySelector(`#like-count-${objectId}`);

        // Update text and like count
        btn.innerHTML = `
            <i class="${data.liked ? 'fa-solid fa-heart' : 'fa-regular fa-heart'}"></i>
            <span id="like-count-${objectId}">${data.like_count}</span>
        `;

        // Add pop animation class
        const heartIcon = btn.querySelector('i');
        heartIcon.classList.add('pop-heart');

        // Remove animation class after it finishes
        heartIcon.addEventListener('animationend', () => {
            heartIcon.classList.remove('pop-heart');
        }, { once: true });
    });
}