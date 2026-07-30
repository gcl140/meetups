/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './accounts/**/*.html',
    './events/**/*.html',
    './chat/**/*.html',
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        wood: {
          50: '#faf6f1',
          100: '#f2e8dc',
          200: '#e4cdb0',
          300: '#d3ab7d',
          400: '#c08a56',
          500: '#a86f3f',
          600: '#8a5732',
          700: '#6b4327',
          800: '#4d2f1c',
          900: '#331f13',
          950: '#1d1109',
        },
        copper: {
          300: '#e6b489',
          400: '#d98e5f',
          500: '#c1703c',
          600: '#a35a2c',
          700: '#824621',
        },
        cream: {
          50: '#fffaf3',
          100: '#fbf1e2',
        },
      },
      fontFamily: {
        display: ['"Fraunces"', 'serif'],
        body: ['"Inter"', 'sans-serif'],
      },
      boxShadow: {
        wood: '0 4px 14px 0 rgba(51, 31, 19, 0.15)',
      },
    },
  },
  plugins: [],
};
