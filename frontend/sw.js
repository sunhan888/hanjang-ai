
/* 한장해결AI 2.0 - 푸시 알림 수신 */

// 새 버전 활성화
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// 서버에서 푸시 메시지를 받으면 알림 표시
self.addEventListener("push", (event) => {
  let path = "/";

  try {
    const data = event.data?.json();
    if (
      typeof data?.url === "string" &&
      data.url.startsWith("/") &&
      !data.url.startsWith("//")
    ) {
      path = data.url;
    }
  } catch (error) {
    // 메시지 데이터가 없어도 기본 알림 표시
  }

  event.waitUntil(
    self.registration.showNotification("한장해결AI", {
      body: "확인할 처리기한이 있어요. 완료 여부를 확인해 주세요.",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: path }
    })
  );
});

// 알림을 누르면 한장해결AI 열기
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const url = new URL(
    event.notification.data?.url || "/",
    self.location.origin
  );

  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then(async (windows) => {
      const existing = windows.find((w) => w.url === url.href);

      if (existing) {
        return existing.focus();
      }

      return self.clients.openWindow(url.href);
    })
  );
});
