package com.anishudupan.notificationtest

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MyFirebaseMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d(TAG, "New FCM Token: $token")
        val intent = Intent(ACTION_NEW_TOKEN).apply {
            putExtra(EXTRA_TOKEN, token)
        }
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent)
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)
        Log.d(TAG, "From: ${remoteMessage.from}")

        val title = remoteMessage.notification?.title 
            ?: remoteMessage.data["title"] 
            ?: "FCM Notification"
        
        val body = remoteMessage.notification?.body 
            ?: remoteMessage.data["body"] 
            ?: "No message body"

        val dataString = if (remoteMessage.data.isNotEmpty()) {
            remoteMessage.data.entries.joinToString { "${it.key}: ${it.value}" }
        } else ""

        val timeString = SimpleDateFormat("HH:mm:ss dd-MMM", Locale.getDefault()).format(Date())

        // 1. Broadcast to MainActivity to update in-app UI list
        val uiIntent = Intent(ACTION_FCM_MESSAGE).apply {
            putExtra(EXTRA_TITLE, title)
            putExtra(EXTRA_BODY, body)
            putExtra(EXTRA_TIME, timeString)
            putExtra(EXTRA_DATA, dataString)
        }
        LocalBroadcastManager.getInstance(this).sendBroadcast(uiIntent)

        // 2. Show Android system notification
        sendSystemNotification(title, body, dataString)
    }

    private fun sendSystemNotification(title: String, body: String, dataString: String) {
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(EXTRA_TITLE, title)
            putExtra(EXTRA_BODY, body)
            putExtra(EXTRA_DATA, dataString)
        }

        // Target API 31+ requires PendingIntent.FLAG_IMMUTABLE or FLAG_MUTABLE
        val pendingIntentFlags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
        } else {
            PendingIntent.FLAG_ONE_SHOT
        }

        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent, pendingIntentFlags
        )

        val channelId = "fcm_default_channel"
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "FCM Notifications",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Channel for FCM push notifications"
                enableVibration(true)
            }
            notificationManager.createNotificationChannel(channel)
        }

        val notificationBuilder = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(pendingIntent)

        if (dataString.isNotEmpty()) {
            notificationBuilder.setStyle(
                NotificationCompat.BigTextStyle()
                    .boldTextTitle(title)
                    .bigText("$body\nData: $dataString")
            )
        }

        notificationManager.notify(System.currentTimeMillis().toInt(), notificationBuilder.build())
    }

    companion object {
        private const val TAG = "FCMService"
        const val ACTION_FCM_MESSAGE = "com.anishudupan.notificationtest.FCM_MESSAGE"
        const val ACTION_NEW_TOKEN = "com.anishudupan.notificationtest.NEW_TOKEN"
        const val EXTRA_TITLE = "extra_title"
        const val EXTRA_BODY = "extra_body"
        const val EXTRA_TIME = "extra_time"
        const val EXTRA_DATA = "extra_data"
        const val EXTRA_TOKEN = "extra_token"
    }
}
