package com.anishudupan.notificationtest

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class NotificationAdapter(
    private val notifications: MutableList<NotificationItem>
) : RecyclerView.Adapter<NotificationAdapter.ViewHolder>() {

    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val tvTitle: TextView = view.findViewById(R.id.tvItemTitle)
        val tvBody: TextView = view.findViewById(R.id.tvItemBody)
        val tvTime: TextView = view.findViewById(R.id.tvItemTime)
        val tvData: TextView = view.findViewById(R.id.tvItemData)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_notification, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = notifications[position]
        holder.tvTitle.text = item.title
        holder.tvBody.text = item.body
        holder.tvTime.text = item.timestamp

        if (item.dataPayload.isNotEmpty()) {
            holder.tvData.visibility = View.VISIBLE
            holder.tvData.text = "Payload: ${item.dataPayload}"
        } else {
            holder.tvData.visibility = View.GONE
        }
    }

    override fun getItemCount(): Int = notifications.size

    fun addNotification(item: NotificationItem) {
        notifications.add(0, item)
        notifyItemInserted(0)
    }
}
