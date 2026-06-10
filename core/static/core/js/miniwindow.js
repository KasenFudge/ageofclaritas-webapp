
// Function to open a Mini Window
function openMiniWindow(event, url) {
    event.preventDefault(); // Prevent the default link action

    // Set Width and Height of the Window
    let width, height;

    if (window.innerWidth <= 768) {
        width = Math.floor(window.innerWidth * 0.8); // 80% of the screen width
        height = Math.floor(window.innerHeight * 0.6); // 60% of the screen height
    }
    else {
        width = Math.floor(window.innerWidth * 0.6); // 60% of the screen width
        height = Math.floor(window.innerHeight * 0.8); // 80% of the screen height
    }

    // Center the mini window
    const left = Math.floor((window.innerWidth - width) / 2);
    const top = Math.floor((window.innerHeight - height) / 2);
  
    // Open the mini window
    window.open(
      url,
      "_blank",
      `width=${width},height=${height},left=${left},top=${top},resizable=no,scrollbars=yes`
    );
}

// Function to load the iframe content dynamically
function loadIframe(url) {
    document.getElementById('iframeContent').src = url;
  }