    private fun registerFcmToken() {
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (!task.isSuccessful) {
                Log.w("FCM", "Fetching FCM registration token failed", task.exception)
                return@addOnCompleteListener
            }

            // Get new FCM registration token
            val token = task.result
            Log.d("FCM", "FCM Token: $token")

            // Send token to backend
            val userId = sessionManager.getUserId()
            if (userId != -1) {
                lifecycleScope.launch(Dispatchers.IO) {
                    try {
                        val response = RetrofitClient.instance.registerDeviceToken(
                            mapOf("user_id" to userId, "fcm_token" to token)
                        )
                        if (response.isSuccessful) {
                            Log.d("FCM", "Token registered with server successfully")
                            sessionManager.clearPendingFcmToken()
                        } else {
                            Log.e("FCM", "Failed to register token: ${response.errorBody()?.string()}")
                        }
                    } catch (e: Exception) {
                        Log.e("FCM", "Error registering FCM token: ${e.message}")
                    }
                }
            }
        }
    }
}
