package com.jsvocnav.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.jsvocnav.app.data.LocalStore
import com.jsvocnav.app.data.SchoolRepository
import com.jsvocnav.app.ui.MainScreen
import com.jsvocnav.app.ui.theme.JsvocNavTheme

/**
 * 唯一 Activity：界面完全由 Compose 绘制。
 *
 * 启动流程刻意不阻塞、不强制联网：先加载本地数据并立即显示，
 * 只有用户主动点「检查数据更新」时才访问网络。
 */
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val repository = SchoolRepository(applicationContext)
        val store = LocalStore(applicationContext)

        setContent {
            JsvocNavTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    MainScreen(
                        context = applicationContext,
                        repository = repository,
                        store = store,
                    )
                }
            }
        }
    }
}
