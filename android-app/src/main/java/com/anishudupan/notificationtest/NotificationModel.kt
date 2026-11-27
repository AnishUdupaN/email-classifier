package com.anishudupan.notificationtest

data class NotificationItem(
    val title: String,
    val body: String,
    val timestamp: String,
    val dataPayload: String = ""
)
