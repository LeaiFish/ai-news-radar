(() => {
  const destination = new URL(window.location.href);
  destination.pathname = destination.pathname.replace(/^\/ai-news-radar(?=\/|$)/, "/ai-perspective");
  if (destination.href !== window.location.href) window.location.replace(destination.href);
})();
