const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const loginFormWrapper = document.getElementById("login-form");
const registerFormWrapper = document.getElementById("register-form");
const switchToRegister = document.getElementById("switch-to-register");

function showLogin() {
    tabLogin.classList.add("active");
    tabRegister.classList.remove("active");
    loginFormWrapper.style.display = "block";
    registerFormWrapper.style.display = "none";
}

function showRegister() {
    tabLogin.classList.remove("active");
    tabRegister.classList.add("active");
    loginFormWrapper.style.display = "none";
    registerFormWrapper.style.display = "block";
}

tabLogin.addEventListener("click", showLogin);
tabRegister.addEventListener("click", showRegister);
switchToRegister.addEventListener("click", showRegister);