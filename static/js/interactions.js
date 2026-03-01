function toggleLike(entryId) {
    fetch(`/interactions/like/${entryId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1],
            'Content-Type': 'application/json',
        },
    })
    .then(res => res.json())
    .then(data => {
        const btn = document.getElementById(`like-btn-${entryId}`);
        btn.innerHTML = `${data.liked ? 'Unlike' : 'Like'} (<span id="like-count-${entryId}">${data.like_count}</span>)`;
    });
}