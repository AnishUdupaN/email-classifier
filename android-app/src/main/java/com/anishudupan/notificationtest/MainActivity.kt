package com.anishudupan.notificationtest

import android.Manifest
import android.content.BroadcastReceiver
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import androidx.recyclerview.widget.LinearLayoutManager
import com.anishudupan.notificationtest.databinding.ActivityMainBinding
import com.google.firebase.messaging.FirebaseMessaging
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val notificationList = mutableListOf<NotificationItem>()
    private lateinit var adapter: NotificationAdapter
    private var fcmToken: String = ""

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            Toast.makeText(this, "Notification permission granted", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(this, "Notification permission denied", Toast.LENGTH_SHORT).show()
        }
    }

    private val messageReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            intent?.let {
                if (it.action == MyFirebaseMessagingService.ACTION_FCM_MESSAGE) {
                    val title = it.getStringExtra(MyFirebaseMessagingService.EXTRA_TITLE) ?: "Notification"
                    val body = it.getStringExtra(MyFirebaseMessagingService.EXTRA_BODY) ?: ""
                    val time = it.getStringExtra(MyFirebaseMessagingService.EXTRA_TIME) ?: ""
                    val data = it.getStringExtra(MyFirebaseMessagingService.EXTRA_DATA) ?: ""

                    addNotificationToUi(title, body, time, data)
                } else if (it.action == MyFirebaseMessagingService.ACTION_NEW_TOKEN) {
                    val token = it.getStringExtra(MyFirebaseMessagingService.EXTRA_TOKEN) ?: ""
                    updateTokenUi(token)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        checkNotificationPermission()
        fetchFcmToken()
        setupListeners()
        handleLaunchIntent(intent)
    }

    private fun setupRecyclerView() {
        adapter = NotificationAdapter(notificationList)
        binding.rvNotifications.layoutManager = LinearLayoutManager(this)
        binding.rvNotifications.adapter = adapter
    }

    private fun checkNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            if (ContextCompat.checkSelfPermission(
                    this,
                    Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun fetchFcmToken() {
        binding.tvToken.text = "Retrieving FCM Token..."
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (!task.isSuccessful) {
                Log.w(TAG, "Fetching FCM registration token failed", task.exception)
                binding.tvToken.text = "Failed to get FCM Token"
                return@addOnCompleteListener
            }

            val token = task.result
            updateTokenUi(token)
        }
    }

    private fun updateTokenUi(token: String) {
        fcmToken = token
        Log.d(TAG, "FCM Token: $token")
        binding.tvToken.text = token
        binding.btnCopyToken.isEnabled = true
    }

    private fun setupListeners() {
        binding.btnCopyToken.setOnClickListener {
            if (fcmToken.isNotEmpty()) {
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = android.content.ClipData.newPlainText("FCM Token", fcmToken)
                clipboard.setPrimaryClip(clip)
                Toast.makeText(this, "FCM Token copied to clipboard!", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun handleLaunchIntent(intent: Intent?) {
        intent?.extras?.let { extras ->
            val title = extras.getString(MyFirebaseMessagingService.EXTRA_TITLE)
            val body = extras.getString(MyFirebaseMessagingService.EXTRA_BODY)
            val data = extras.getString(MyFirebaseMessagingService.EXTRA_DATA) ?: ""

            if (!title.isNullOrEmpty() || !body.isNullOrEmpty()) {
                val timeString = SimpleDateFormat("HH:mm:ss dd-MMM", Locale.getDefault()).format(Date())
                addNotificationToUi(title ?: "App Opened", body ?: "", timeString, data)
            }
        }
    }

    private fun addNotificationToUi(title: String, body: String, time: String, data: String) {
        val item = NotificationItem(title, body, time, data)
        adapter.addNotification(item)
        binding.rvNotifications.scrollToPosition(0)
        binding.tvEmptyState.visibility = View.GONE
    }

    override fun onStart() {
        super.onStart()
        val filter = IntentFilter().apply {
            addAction(MyFirebaseMessagingService.ACTION_FCM_MESSAGE)
            addAction(MyFirebaseMessagingService.ACTION_NEW_TOKEN)
        }
        LocalBroadcastManager.getInstance(this).registerReceiver(messageReceiver, filter)
    }

    override fun onStop() {
        super.onStop()
        LocalBroadcastManager.getInstance(this).unregisterReceiver(messageReceiver)
    }

    companion object {
        private const val TAG = "MainActivity"
    }
}
