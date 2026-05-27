// import { StrictMode } from "react";
// import { createRoot } from "react-dom/client";
// import { BrowserRouter } from "react-router-dom";
// import "./index.css";
// import App from "./App.jsx";

// /* Force browser to NOT remember old scroll position */
// if ("scrollRestoration" in window.history) {
//   window.history.scrollRestoration = "manual";
// }

// function forceScrollTop() {
//   window.scrollTo(0, 0);

//   document.documentElement.scrollTop = 0;
//   document.body.scrollTop = 0;

//   const root = document.getElementById("root");
//   if (root) {
//     root.scrollTop = 0;
//     root.scrollLeft = 0;
//   }
// }

// /* Run before React renders */
// forceScrollTop();

// /* Run after browser/React tries to restore old position */
// window.addEventListener("beforeunload", () => {
//   forceScrollTop();
// });

// window.addEventListener("load", () => {
//   forceScrollTop();

//   requestAnimationFrame(forceScrollTop);
//   setTimeout(forceScrollTop, 0);
//   setTimeout(forceScrollTop, 50);
//   setTimeout(forceScrollTop, 150);
//   setTimeout(forceScrollTop, 300);
// });

// createRoot(document.getElementById("root")).render(
//   <StrictMode>
//     <BrowserRouter>
//       <App />
//     </BrowserRouter>
//   </StrictMode>
// );

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles/index.css";
import App from "./App.jsx";

/* Force browser to NOT remember old scroll position */
if ("scrollRestoration" in window.history) {
  window.history.scrollRestoration = "manual";
}

function forceScrollTop() {
  window.scrollTo(0, 0);

  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;

  const root = document.getElementById("root");
  if (root) {
    root.scrollTop = 0;
    root.scrollLeft = 0;
  }
}

/* Run before React renders */
forceScrollTop();

/* Run after browser/React tries to restore old position */
window.addEventListener("beforeunload", () => {
  forceScrollTop();
});

window.addEventListener("load", () => {
  forceScrollTop();

  requestAnimationFrame(forceScrollTop);
  setTimeout(forceScrollTop, 0);
  setTimeout(forceScrollTop, 50);
  setTimeout(forceScrollTop, 150);
  setTimeout(forceScrollTop, 300);
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);