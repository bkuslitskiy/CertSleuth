/** Design-system build (see static/css/src/input.css for tokens + component layer).
 *  darkMode keys off the existing data-theme toggle (static/js/theme.js). */
module.exports = {
  content: ["./templates/**/*.html"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {},
  },
  plugins: [],
};
