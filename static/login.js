console.log("login.js loaded successfully!");
const demoUsers = { 
     customer: {
        email: "customer@lockservice.demo",
        password: "Demo1234!",
        destination: "/customer/dashboard"
    },
    
    staff: {
        email: "staff@lockservice.demo",
        password: "Demo1234!",
        destination: "/staff/dashboard"
    }
}

// Connecting to HTML files
const loginForm = document.getElementById("loginForm")

if (loginForm){
    const roleInput = document.getElementById("role");
    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");
    const loginMessage = document.getElementById("loginMessage");
    
    loginForm.addEventListener("submit", function(event)
    {

        event.preventDefault();
        console.log("Login form submitted!");

        // login validation / redirection
        const role = roleInput.value;
        const email = emailInput.value.trim().toLowerCase();
        const password = passwordInput.value;

        const user =  demoUsers[role];

        // checking if the credentials match
        if ( user && email === user.email && password === user.password)
        {
            sessionStorage.setItem("lockserviceRole", role);

            window.location.href = user.destination;
        }
        else {
            loginMessage.textContext =  "Invalid email or  password";
        }

    });

    // show and hide password
    const showPassword = document.getElementById("showPassword");

    showPassword.addEventListener("change", function(){
        passwordInput.type = this.checked ? "text" : "password";
    });

    // demo cred. 
    const fillDemo = document.getElementById("fillDemo");

    fillDemo.addEventListener("click", function(){
        const selectedRole = roleInput.value;
        const user = demoUsers[selectedRole];

        emailInput.value = user.email;
        passwordInput.value = user.password;
        loginMessage.textContent = "";
    });
}

const requiredRole = document.body.dataset.dashboardRole;

if (requiredRole) {
    const currentRole = sessionStorage.getItem("lockserviceRole");

    if (currentRole !== requiredRole) {
        window.location.replace("/login");
    }
}