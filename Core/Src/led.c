#include "led.h"

void led_init(led_t *led, Led_TypeDef id, uint32_t delay_ms){
    led->id = id;
    led->delay_ms = delay_ms;
    led->lastBliknk = 0;

}
void led_updates(led_t leds[], uint8_t num_leds){
    for (uint8_t i = 0; i < num_leds; i++){
        if (HAL_GetTick() - leds[i].lastBliknk >= leds[i].delay_ms){
            BSP_LED_Toggle(leds[i].id);
            leds[i].lastBliknk = HAL_GetTick();
        }
    }
}
void led_set_delay(led_t *led, uint32_t delay_ms){
    led->delay_ms = delay_ms;
}

