function renderReviewStars(rating) {
  return '★'.repeat(rating) + '☆'.repeat(5 - rating);
}

function updateReviewsDisplay(reviews, stats) {
  const statValues = document.querySelectorAll('.stat-value');
  if (statValues.length >= 2) {
    statValues[0].textContent = stats.total;
    statValues[1].textContent = stats.average_rating;
  }

  if (stats.total > 0) {
    for (let rating = 1; rating <= 5; rating += 1) {
      const bar = document.querySelectorAll('.rating-bar')[5 - rating];
      if (!bar) {
        continue;
      }
      const percentage = (stats.rating_distribution[rating] / stats.total) * 100;
      const fill = bar.querySelector('.rating-bar-fill');
      const count = bar.querySelector('.rating-count');
      if (fill) {
        fill.style.width = `${percentage}%`;
      }
      if (count) {
        count.textContent = stats.rating_distribution[rating];
      }
    }
  }

  const reviewsList = document.getElementById('reviews-list');
  if (!reviewsList) {
    return;
  }

  let reviewsHtml = `<h2>💬 User Reviews (${stats.total})</h2>`;

  if (reviews.length > 0) {
    reviews.forEach((review) => {
      reviewsHtml += `
        <div class="review-item">
          <div class="review-header">
            <div class="review-rating">${renderReviewStars(review.rating)}</div>
            <div class="review-meta">${review.timestamp} | User: ${review.user_id}</div>
          </div>
          ${review.text ? `<div class="review-text">${review.text}</div>` : ''}
        </div>
      `;
    });
  } else {
    reviewsHtml += '<div class="no-reviews">No reviews yet. Be the first to share your experience!</div>';
  }

  reviewsList.innerHTML = reviewsHtml;
}

async function refreshReviews(path) {
  const response = await fetch(`/${path}/reviews/list`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error('Failed to refresh reviews');
  }
  const data = await response.json();
  updateReviewsDisplay(data.reviews, data.stats);
}

document.addEventListener('DOMContentLoaded', () => {
  const scriptEnabled = document.body.dataset.scriptEnabled === 'true';
  const path = document.body.dataset.path;
  const reviewForm = document.getElementById('review-form');

  if (!scriptEnabled || !path || !reviewForm) {
    return;
  }

  setInterval(() => {
    refreshReviews(path).catch(() => {});
  }, 30000);

  reviewForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const formData = new FormData(reviewForm);
    const response = await fetch(`/${path}/reviews/submit`, {
      method: 'POST',
      body: formData,
    });

    const payload = await response.json();
    document.querySelectorAll('.message').forEach((element) => element.remove());

    const messageBox = document.createElement('div');
    messageBox.className = `message ${payload.success ? 'success' : 'error'}`;
    messageBox.textContent = payload.message;
    reviewForm.parentNode.insertBefore(messageBox, reviewForm);

    if (payload.success) {
      reviewForm.reset();
      await refreshReviews(path);
    }
  });
});
