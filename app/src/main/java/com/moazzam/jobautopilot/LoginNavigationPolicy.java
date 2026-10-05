package com.moazzam.jobautopilot;

import java.net.URI;

final class LoginNavigationPolicy {
    static boolean isAllowed(String url, boolean mainFrame) {
        try {
            URI uri = URI.create(url);
            if (!mainFrame && "about:blank".equals(url)) return true;
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                    || uri.getUserInfo() != null) return false;
            // HTTPS verification frames must work without opening other top-level sites.
            if (!mainFrame) return true;
            String host = uri.getHost().toLowerCase(java.util.Locale.ROOT);
            return host.equals("naukri.com") || host.endsWith(".naukri.com");
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }
}
