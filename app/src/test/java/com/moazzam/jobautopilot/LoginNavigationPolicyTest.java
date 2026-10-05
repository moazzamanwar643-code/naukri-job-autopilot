package com.moazzam.jobautopilot;

import org.junit.Test;
import static org.junit.Assert.*;

public class LoginNavigationPolicyTest {
    @Test public void allowsNaukriNavigation() {
        assertTrue(LoginNavigationPolicy.isAllowed("https://www.naukri.com/nlogin/login#email", true));
        assertTrue(LoginNavigationPolicy.isAllowed("https://naukri.com/mnjuser/homepage", true));
    }
    @Test public void permitsSecureVerificationFramesOnly() {
        assertTrue(LoginNavigationPolicy.isAllowed("https://www.google.com/recaptcha/api2/anchor", false));
        assertTrue(LoginNavigationPolicy.isAllowed("about:blank", false));
        assertFalse(LoginNavigationPolicy.isAllowed("http://www.google.com/recaptcha", false));
        assertFalse(LoginNavigationPolicy.isAllowed("file:///data/local/secret", false));
        assertFalse(LoginNavigationPolicy.isAllowed("javascript:alert(1)", false));
    }
    @Test public void blocksUntrustedTopLevelNavigation() {
        assertFalse(LoginNavigationPolicy.isAllowed("https://naukri.com.evil.example/login", true));
        assertFalse(LoginNavigationPolicy.isAllowed("https://evilnaukri.com/login", true));
        assertFalse(LoginNavigationPolicy.isAllowed("https://naukri.com@evil.example", true));
        assertFalse(LoginNavigationPolicy.isAllowed("https://www.google.com/", true));
        assertFalse(LoginNavigationPolicy.isAllowed("intent://login", true));
        assertFalse(LoginNavigationPolicy.isAllowed("about:blank", true));
    }
}
