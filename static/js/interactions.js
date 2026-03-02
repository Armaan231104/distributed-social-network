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
        btn.innerHTML = `${data.liked ? 'Unlike' : 'Like'} (<span id="like-count-${objectId}">${data.like_count}</span>)`;
        btn.classList.toggle('liked', data.liked);
    });
}