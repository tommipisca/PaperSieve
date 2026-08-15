/**
 * Progressive enhancement for the "save/remove favorite" forms.
 *
 * Without this file, every save/remove button is a normal HTML form that
 * posts to the server and reloads the page — that still works perfectly
 * fine, it's just a little jarring (full reload, scroll jumps to top).
 *
 * With this file, we intercept those same form submissions, send them in
 * the background with fetch(), and update just the button (or remove the
 * card, on the favorites page) in place. If anything goes wrong — fetch
 * not supported, network error, server error — we fall back to letting
 * the form submit normally, so the feature never actually breaks.
 */

document.addEventListener("submit", handleFavoriteFormSubmit);
document.addEventListener("submit", handleSearchFormSubmit);

// arXiv's API 500s on a literal "browse everything" query (all
// categories, no keyword, no author) — see the matching check and
// comment in routes.py. That's the authoritative fix: it works with
// JavaScript off, and covers direct/bookmarked URLs too. This is purely
// an enhancement on top of it — catching the same case before the form
// is even submitted, so visitors see the message instantly instead of
// after a round trip to the server.
const NEEDS_KEYWORD_OR_AUTHOR_MESSAGE =
  "Enter a keyword or author, or choose a specific category — arXiv " +
  "doesn't support browsing every category with nothing to search for.";

function handleSearchFormSubmit(event) {
  const form = event.target;

  if (!form.matches(".search-form")) {
    return;
  }

  const category = form.querySelector("#category");
  const query = form.querySelector("#q");
  const author = form.querySelector("#author");

  if (!category || !query || !author) {
    return;
  }

  const isAllCategories = category.value === "all";
  const hasKeywordOrAuthor = query.value.trim() !== "" || author.value.trim() !== "";

  if (isAllCategories && !hasKeywordOrAuthor) {
    event.preventDefault();
    showSearchValidationMessage(form);
    query.focus();
  }
}

function showSearchValidationMessage(form) {
  let message = form.parentElement.querySelector(".search-form__validation");

  if (!message) {
    message = document.createElement("p");
    message.className = "alert search-form__validation";
    message.setAttribute("role", "alert");
    form.insertAdjacentElement("afterend", message);
  }

  message.textContent = NEEDS_KEYWORD_OR_AUTHOR_MESSAGE;
}

async function handleFavoriteFormSubmit(event) {
  const form = event.target;

  if (!form.matches(".favorite-form")) {
    return;
  }

  // Set by the fallback path below, right before re-submitting for real:
  // lets that second, native submission through instead of being caught
  // (and re-intercepted) by this same handler again.
  if (form.dataset.jsFallback) {
    return;
  }

  event.preventDefault();

  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });

    if (!response.ok) {
      throw new Error(`Unexpected response status: ${response.status}`);
    }

    applyFavoriteChange(form);
  } catch (error) {
    console.error(
      "Saving/removing the favorite in the background failed, falling back " +
        "to a normal page submit:",
      error
    );
    form.dataset.jsFallback = "true";
    if (form.requestSubmit) {
      form.requestSubmit();
    } else {
      form.submit();
    }
  }
}

function applyFavoriteChange(form) {
  const action = form.dataset.action; // "add" or "remove"
  const onFavoritesPage = document.body.dataset.page === "favorites";

  if (action === "remove" && onFavoritesPage) {
    // On the favorites page there's nothing to toggle back to: the paper
    // just shouldn't be listed anymore.
    const card = form.closest(".paper-card");
    if (card) {
      card.remove();
    }
    updateFavoritesCount();
    return;
  }

  // On the search page, flip to the matching sibling form (add <-> remove)
  // instead of removing anything.
  const otherAction = action === "add" ? "remove" : "add";
  const actionsContainer = form.closest(".paper-card__actions");
  const sibling = actionsContainer
    ? actionsContainer.querySelector(`.favorite-form[data-action="${otherAction}"]`)
    : null;

  form.hidden = true;
  if (sibling) {
    sibling.hidden = false;
    // The button the visitor just activated is now hidden (and no longer
    // focusable), which would otherwise silently drop focus back to
    // <body>. Move it to the button that took its place so keyboard and
    // screen reader users land on the new state instead of losing their
    // position on the page.
    const siblingButton = sibling.querySelector("button");
    if (siblingButton) {
      siblingButton.focus();
    }
  }
}

function updateFavoritesCount() {
  const heading = document.getElementById("favorites-heading");
  if (!heading) {
    return;
  }

  const remaining = document.querySelectorAll(".results .paper-card").length;

  if (remaining === 0) {
    // Simplest correct way to show the proper "no favorites yet" empty
    // state (with its message and link back to search) is to just reload
    // the now-empty page rather than duplicating that markup here in JS.
    window.location.reload();
    return;
  }

  heading.textContent = `${remaining} saved paper${remaining === 1 ? "" : "s"}`;
  // Same reasoning as above: the card (and the button inside it) that
  // just got removed is gone, so move focus to the nearest stable
  // landmark rather than letting it silently fall back to <body>.
  heading.focus();
}
