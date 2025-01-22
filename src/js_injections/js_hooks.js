console.log("Loaded HWPG")

// Request experiment
const fn = () => {console.log("Stopped registration of service worker")};
navigator.serviceWorker.register = () => new Promise(fn, fn);
