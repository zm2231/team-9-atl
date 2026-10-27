import "@testing-library/jest-dom/vitest";

// jsdom has no layout, so it leaves out Element.scrollTo; ChatPanel calls it to follow new messages.
if (typeof Element !== "undefined" && !Element.prototype.scrollTo) Element.prototype.scrollTo = () => {};
